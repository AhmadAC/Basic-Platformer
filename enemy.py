# enemy.py
# -*- coding: utf-8 -*-
## version 1.0.0.20 (Refactored into multiple handlers)
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
"""
import pygame
import constants as C

# --- Import Base Class ---
from enemy_base import EnemyBase

# --- Import Handler Modules ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY (Main): logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func

try:
    from enemy_ai_handler import enemy_ai_update, set_enemy_new_patrol_target
    from enemy_combat_handler import check_enemy_attack_collisions, enemy_take_damage # Renamed from take_damage in Enemy class
    from enemy_network_handler import get_enemy_network_data, set_enemy_network_data
    from enemy_state_handler import set_enemy_state
    from enemy_animation_handler import update_enemy_animation
    from enemy_status_effects import (
        update_enemy_status_effects,
        apply_aflame_effect as apply_aflame_to_enemy, # Alias to avoid name clash if Enemy had similar method
        apply_freeze_effect as apply_freeze_to_enemy,
        petrify_enemy as petrify_this_enemy,
        stomp_kill_enemy as stomp_kill_this_enemy,
        smash_petrified_enemy as smash_this_petrified_enemy
    )
    from enemy_physics_handler import update_enemy_physics_and_collisions
except ImportError as e:
    critical(f"ENEMY (Main) CRITICAL: Failed to import one or more handler modules: {e}")
    # This would likely make the game unrunnable, consider a more graceful exit or error display
    raise

class Enemy(EnemyBase):
    def __init__(self, start_x, start_y, patrol_area=None, enemy_id=None, color_name=None):
        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name)
        if not self._valid_init:
            critical(f"Enemy (ID: {self.enemy_id}) did not initialize correctly in EnemyBase. Main Enemy class init incomplete.")
            return
        # Initialize patrol target explicitly after base init and potential color/animation setup
        set_enemy_new_patrol_target(self)
        debug(f"Enemy (ID: {self.enemy_id}, Color: {self.color_name}) main class initialized. Patrol target set.")


    # --- Public Interface for Status Effects ---
    def apply_aflame_effect(self):
        """Public method to make this enemy instance aflame."""
        apply_aflame_to_enemy(self)

    def apply_freeze_effect(self):
        """Public method to make this enemy instance frozen."""
        apply_freeze_to_enemy(self)

    def petrify(self):
        """Public method to make this enemy instance petrified."""
        petrify_this_enemy(self)

    def smash_petrification(self):
        """Public method to smash this petrified enemy."""
        smash_this_petrified_enemy(self)

    def stomp_kill(self):
        """Public method to initiate stomp death for this enemy."""
        stomp_kill_this_enemy(self)

    # --- Combat ---
    def take_damage(self, damage_amount_taken):
        """Handles this enemy instance taking damage."""
        enemy_take_damage(self, damage_amount_taken) # Calls the function from enemy_combat_handler

    # --- Network ---
    def get_network_data(self):
        """Gets network data for this enemy."""
        return get_enemy_network_data(self)

    def set_network_data(self, received_network_data):
        """Sets network data for this enemy."""
        set_enemy_network_data(self, received_network_data)

    # --- State and Animation (delegated) ---
    def set_state(self, new_state: str):
        """Sets the logical state of the enemy using the state handler."""
        set_enemy_state(self, new_state)

    def animate(self):
        """Updates the enemy's animation using the animation handler."""
        update_enemy_animation(self)

    # --- Main Update Loop ---
    def update(self, dt_sec, players_list_for_logic, platforms_group, hazards_group, all_enemies_list):
        if not self._valid_init:
            return

        current_time_ms = pygame.time.get_ticks()

        # 1. Update and check overriding status effects
        # This function will handle timers, damage ticks for aflame, and state transitions out of effects.
        # It returns True if an effect is active and overriding normal updates.
        if update_enemy_status_effects(self, current_time_ms, platforms_group):
            # If petrified, physics handler might still need to apply gravity if it's not on ground
            if self.is_petrified and not self.is_stone_smashed and not self.on_ground:
                update_enemy_physics_and_collisions(self, dt_sec, platforms_group, hazards_group, []) # Minimal physics for falling stone
            update_enemy_animation(self) # Ensure animation reflects the status effect
            if self.is_dead and self.death_animation_finished and self.alive(): # Check if effect killed it
                self.kill()
            return # Status effect is managing the enemy

        # 2. Handle regular death (if not already handled by a status effect like smashed/stomp)
        if self.is_dead:
            if self.alive(): # Still in sprite groups
                if not self.death_animation_finished:
                    # Simplified physics for regular death (e.g., falling if not on ground)
                    # This could also be moved into enemy_physics_handler with a specific flag
                    if not self.on_ground:
                        self.vel.y += self.acc.y # Apply gravity
                        self.vel.y = min(self.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))
                        self.pos.y += self.vel.y
                        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
                        # Basic ground check for dead falling enemy
                        self.on_ground = False
                        for platform_sprite in pygame.sprite.spritecollide(self, platforms_group, False):
                            if self.vel.y > 0 and self.rect.bottom > platform_sprite.rect.top and \
                               (self.pos.y - self.vel.y) <= platform_sprite.rect.top + 1:
                                self.rect.bottom = platform_sprite.rect.top
                                self.on_ground = True; self.vel.y = 0; self.acc.y = 0
                                self.pos.y = self.rect.bottom; break
                update_enemy_animation(self) # Continue death animation
                if self.death_animation_finished:
                    self.kill()
            return # Dead enemy does no more

        # 3. AI Update (determines desired actions, sets acc.x, state for attacks)
        enemy_ai_update(self, players_list_for_logic)

        # 4. Physics and Collisions
        # This will apply movement based on acc, handle friction, and all collisions
        update_enemy_physics_and_collisions(
            self,
            dt_sec,
            platforms_group,
            hazards_group,
            players_list_for_logic + [e for e in all_enemies_list if e is not self] # Pass all other relevant characters
        )

        # 5. Combat Actions (check if current attack hits anyone)
        if self.is_attacking: # is_attacking flag is set by AI or state handler
            check_enemy_attack_collisions(self, players_list_for_logic)

        # 6. Animation
        # This should be called after all state changes and physics updates for the frame
        update_enemy_animation(self)

        # Final check (though should be covered by death_animation_finished in status/death handling)
        if self.is_dead and self.death_animation_finished and self.alive():
            self.kill()

    def reset(self):
        """Resets the enemy to its initial spawn state."""
        super().reset() # Calls EnemyBase.reset()
        set_enemy_new_patrol_target(self) # Set initial patrol target after core reset
        set_enemy_state(self, 'idle')    # Ensure logical and visual state is idle
        debug(f"Enemy (ID: {self.enemy_id}) fully reset. State: {self.state}, AI State: {self.ai_state}")