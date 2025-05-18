# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0.1.2 (Reset/Pause events process even if player is dead)
Handles the game logic for the local couch co-op (two players on one machine) mode.
"""
import pygame
import traceback
from typing import Dict, List # Added List

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL COUCH_PLAY_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}") # Defined error for fallback
    def critical(msg): print(f"CRITICAL: {msg}")

import constants as C
from game_state_manager import reset_game_state # For resetting the game
from enemy import Enemy # For type hinting if needed
from items import Chest # For type hinting if needed
from statue import Statue # Import Statue for interaction
import game_ui # For drawing the scene
import config as game_config # For player control configurations

def run_couch_play_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                        fonts: dict, game_elements_ref: dict, app_status_obj):
    """
    Runs the main game loop for couch co-op mode.

    Args:
        screen (pygame.Surface): The main game screen surface.
        clock (pygame.time.Clock): The Pygame clock object for controlling FPS.
        fonts (dict): A dictionary of loaded Pygame font objects.
        game_elements_ref (dict): A dictionary containing all active game elements
                                  (players, enemies, platforms, etc.).
        app_status_obj (Any): An object with an 'app_running' boolean attribute
                              to control the overall application loop.
    """
    info("CouchPlayLogic: Entering Couch Play mode.")
    pygame.display.set_caption(f"Platformer - Couch Co-op (P1: {game_config.CURRENT_P1_INPUT_DEVICE}, P2: {game_config.CURRENT_P2_INPUT_DEVICE} | Reset: Mapped Keys / Q)")
    current_width, current_height = screen.get_size()

    # Get player instances from game_elements
    p1 = game_elements_ref.get("player1")
    p2 = game_elements_ref.get("player2")

    couch_game_active = True
    while couch_game_active and app_status_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0 # Delta time in seconds
        now_ticks_couch = pygame.time.get_ticks() # Current game time in milliseconds

        # Get all Pygame events and current keyboard state
        pygame_events = pygame.event.get()
        keys_pressed = pygame.key.get_pressed()

        # Flags for universal actions (reset game, pause/exit mode)
        any_player_requested_reset = False
        any_player_requested_pause = False # Pause in couch mode usually means exit to menu

        # --- Process Pygame Events for Global Actions (Escape, Q, debug keys) ---
        for event in pygame_events:
            if event.type == pygame.QUIT: # Window close button
                couch_game_active = False
                app_status_obj.app_running = False # Signal main app to quit
                break
            if event.type == pygame.VIDEORESIZE: # Window resized
                if not screen.get_flags() & pygame.FULLSCREEN: # Ignore if fullscreen (resize often internal)
                    current_width, current_height = max(320,event.w), max(240,event.h)
                    screen = pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    if game_elements_ref.get("camera"): # Update camera with new screen dimensions
                        game_elements_ref["camera"].set_screen_dimensions(current_width, current_height)
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: # K_ESCAPE exits couch play mode
                    any_player_requested_pause = True 
                    info("Couch Play: Global ESC key pressed, treating as pause/exit mode.")
                    break # Stop processing further events this frame if exiting
                
                if event.key == pygame.K_q: # Developer reset key
                    any_player_requested_reset = True
                    info("Couch Play: Dev 'Q' key reset triggered.")

                # Player-specific self-harm/heal debug keys (useful for testing)
                if p1 and p1._valid_init:
                    if event.key == pygame.K_h and hasattr(p1, 'self_inflict_damage'):
                        p1.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_g and hasattr(p1, 'heal_to_full'):
                        p1.heal_to_full()
                if p2 and p2._valid_init:
                    if event.key == pygame.K_n and hasattr(p2, 'self_inflict_damage'): # Different keys for P2 debug
                        p2.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_m and hasattr(p2, 'heal_to_full'):
                        p2.heal_to_full()
        
        # Exit main loop if app quit or couch mode ended by global ESC
        if not app_status_obj.app_running or not couch_game_active: break
        if any_player_requested_pause: # If global ESC was pressed to pause/exit
            couch_game_active = False; break


        # --- Process P1 input ---
        p1_action_events: Dict[str, bool] = {} # Stores one-time events like "jump_pressed"
        if p1 and p1._valid_init and hasattr(p1, 'process_input'):
            # process_input is called even if P1 is dead to capture universal events like reset/pause
            p1_action_events = p1.process_input(pygame_events, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), keys_pressed_override=keys_pressed)
        
        # Check for universal events (pause/reset) from P1's input
        if p1_action_events.get("pause"):
            any_player_requested_pause = True
            info("Couch Play: P1 pause action detected from input.")
        if p1_action_events.get("reset"):
            any_player_requested_reset = True
            info("Couch Play: P1 reset action detected from input.")
        
        if any_player_requested_pause: # Check if P1 paused the game
            couch_game_active = False; break


        # --- Process P2 input ---
        p2_action_events: Dict[str, bool] = {}
        if p2 and p2._valid_init and hasattr(p2, 'process_input') and p2.control_scheme is not None:
            # process_input called even if P2 is dead for reset/pause events
            p2_action_events = p2.process_input(pygame_events, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), keys_pressed_override=keys_pressed)

        # Check for universal events (pause/reset) from P2's input
        if p2_action_events.get("pause"):
            any_player_requested_pause = True
            info("Couch Play: P2 pause action detected from input.")
        if p2_action_events.get("reset"):
            any_player_requested_reset = True
            info("Couch Play: P2 reset action detected from input.")

        if any_player_requested_pause: # Check if P2 paused the game
            couch_game_active = False; break


        # --- Game Action Logic ---
        if any_player_requested_reset:
            info("Couch Play: Game state reset initiated.")
            # reset_game_state handles resetting players, enemies, chest
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
            # Ensure players are re-added to sprite groups if they were killed then reset
            if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p1)
            if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p2)

        # --- Update P1 (Host player) ---
        # P1's Player.update method handles physics, state changes based on input, etc.
        # Input events (p1_action_events) are not directly passed to update; Player.update
        # relies on Player attributes set by its own process_input call.
        if p1 and p1._valid_init: 
            other_players_for_p1_update = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref # For projectile spawning
            p1.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("ladder_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("hazard_sprites", pygame.sprite.Group()),
                      other_players_for_p1_update, # List of other players for collision
                      game_elements_ref.get("enemy_list", [])) # List of enemies for collision/targeting

        # --- Update P2 (Second local player) ---
        if p2 and p2._valid_init:
            other_players_for_p2_update = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("ladder_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("hazard_sprites", pygame.sprite.Group()),
                      other_players_for_p2_update,
                      game_elements_ref.get("enemy_list", []))

        # --- Update Enemies ---
        active_players_for_enemy_ai = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy_couch in list(game_elements_ref.get("enemy_list", [])): # Iterate copy if list can be modified
            if enemy_couch._valid_init:
                enemy_couch.update(dt_sec, active_players_for_enemy_ai,
                                   game_elements_ref.get("platform_sprites", pygame.sprite.Group()),
                                   game_elements_ref.get("hazard_sprites", pygame.sprite.Group()),
                                   game_elements_ref.get("enemy_list", [])) # Pass list of all enemies for enemy-enemy collision
                # Server-authoritative removal of enemies if their death animation is finished
                if enemy_couch.is_dead and hasattr(enemy_couch, 'death_animation_finished') and \
                   enemy_couch.death_animation_finished and enemy_couch.alive():
                    debug(f"Couch Play: Auto-killing enemy {enemy_couch.enemy_id} as death anim finished.")
                    enemy_couch.kill() # Remove from all sprite groups

        # --- Update Statues ---
        statue_objects_list_couch: List[Statue] = game_elements_ref.get("statue_objects", [])
        for statue_instance_couch in statue_objects_list_couch:
            if hasattr(statue_instance_couch, 'update'):
                statue_instance_couch.update(dt_sec) # Handles smash animation and self.kill()

        # --- Update Projectiles ---
        # Create a group of all characters/objects that projectiles can hit
        hittable_targets_couch_group = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_targets_couch_group.add(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_targets_couch_group.add(p2)
        
        for enemy_instance_proj_target in game_elements_ref.get("enemy_list", []):
            if enemy_instance_proj_target and enemy_instance_proj_target.alive() and \
               enemy_instance_proj_target._valid_init and not getattr(enemy_instance_proj_target, 'is_petrified', False):
                hittable_targets_couch_group.add(enemy_instance_proj_target)
        
        for statue_target_couch in statue_objects_list_couch: # Add active statues to hittable group
            if statue_target_couch.alive() and hasattr(statue_target_couch, 'is_smashed') and \
               not statue_target_couch.is_smashed: # Can only hit non-smashed statues
                hittable_targets_couch_group.add(statue_target_couch)
        
        # Ensure projectiles have access to game elements (e.g., for spawning sub-projectiles if any)
        for proj_instance_couch in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if hasattr(proj_instance_couch, 'game_elements_ref') and proj_instance_couch.game_elements_ref is None:
                proj_instance_couch.game_elements_ref = game_elements_ref
        
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(
            dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), hittable_targets_couch_group
        )

        # --- Update Collectibles (Chests, etc.) ---
        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)

        # --- Chest Interaction Logic ---
        # Uses action_events captured earlier from player input processing.
        couch_current_chest = game_elements_ref.get("current_chest")
        if isinstance(couch_current_chest, Chest) and couch_current_chest.alive() and \
           not couch_current_chest.is_collected_flag_internal: # Check if chest can be collected
            
            player_who_interacted_with_chest_couch = None
            # Check P1 interaction
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1, 'is_petrified', False) and \
               pygame.sprite.collide_rect(p1, couch_current_chest) and p1_action_events.get("interact", False):
                player_who_interacted_with_chest_couch = p1
            # Check P2 interaction (if P1 didn't already interact this frame)
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2, 'is_petrified', False) and \
                 pygame.sprite.collide_rect(p2, couch_current_chest) and p2_action_events.get("interact", False):
                player_who_interacted_with_chest_couch = p2
            
            if player_who_interacted_with_chest_couch:
                couch_current_chest.collect(player_who_interacted_with_chest_couch) # Trigger chest collection

        # --- Update Camera ---
        couch_camera = game_elements_ref.get("camera")
        if couch_camera:
            camera_focus_target_couch = None
            # Prioritize P1 if alive and not dead/petrified
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1, 'is_petrified', False):
                camera_focus_target_couch = p1
            # Else, try P2 if alive and not dead/petrified
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2, 'is_petrified', False):
                camera_focus_target_couch = p2
            # Fallbacks if primary targets are dead/petrified (still show them if they exist)
            elif p1 and p1.alive() and p1._valid_init and (p1.is_dead or getattr(p1, 'is_petrified', False)):
                 camera_focus_target_couch = p1
            elif p2 and p2.alive() and p2._valid_init and (p2.is_dead or getattr(p2, 'is_petrified', False)):
                 camera_focus_target_couch = p2
            
            if camera_focus_target_couch: couch_camera.update(camera_focus_target_couch)
            else: couch_camera.static_update() # If no valid target, camera remains static

        # --- Draw Scene ---
        try:
            game_ui.draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_couch)
        except Exception as e_draw:
            error(f"Couch Play draw error: {e_draw}", exc_info=True)
            couch_game_active=False; break # Critical draw error, exit mode
        
        pygame.display.flip() # Update the full display

    info("CouchPlayLogic: Exiting Couch Play mode.")
    # Game elements (players, enemies, etc.) persist in game_elements_ref
    # for potential reuse or cleanup by the main loop.