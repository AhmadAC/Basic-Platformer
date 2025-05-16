########## START OF FILE: items.py ##########

# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
Uses resource_path helper for PyInstaller compatibility.
"""
# version 1.0.0.3 (Chest state machine, fade, timed heal)
import pygame
import os
import sys 
import random

import constants as C
from assets import load_gif_frames, resource_path
try:
    from logger import debug, info, warning
except ImportError:
    def debug(msg): print(f"DEBUG_ITEMS: {msg}")
    def info(msg): print(f"INFO_ITEMS: {msg}")
    def warning(msg): print(f"WARNING_ITEMS: {msg}")


class Chest(pygame.sprite.Sprite):
    """
    A chest that opens, stays open for a bit, fades, and then restores player health.
    """
    def __init__(self, x, y):
        super().__init__()
        self._valid_init = True

        # Load closed frames
        full_chest_closed_path = resource_path(C.CHEST_CLOSED_SPRITE_PATH)
        self.frames_closed = load_gif_frames(full_chest_closed_path)
        if not self.frames_closed or (len(self.frames_closed) == 1 and self.frames_closed[0].get_size() == (30,40) and self.frames_closed[0].get_at((0,0)) == C.RED):
            warning(f"Chest: Failed to load closed frames from '{full_chest_closed_path}'. Using placeholder.")
            self._valid_init = False
            self.frames_closed = [self._create_placeholder_surface(C.YELLOW, "ClosedErr")]

        # Load open frames
        full_chest_open_path = resource_path(C.CHEST_OPEN_SPRITE_PATH)
        self.frames_open = load_gif_frames(full_chest_open_path)
        if not self.frames_open or (len(self.frames_open) == 1 and self.frames_open[0].get_size() == (30,40) and self.frames_open[0].get_at((0,0)) == C.RED):
            warning(f"Chest: Failed to load open frames from '{full_chest_open_path}'. Using placeholder.")
            # If open frames fail, this is significant for the opening animation.
            # We'll use a placeholder, but the chest might not look right when "open".
            self.frames_open = [self._create_placeholder_surface(C.BLUE, "OpenErr")]
            # Consider if self._valid_init should be False here if opening is crucial. For now, allow if closed is okay.

        self.state = 'closed' # 'closed', 'opening', 'opened', 'fading', 'killed'
        self.is_collected_flag_internal = False # True once collection process starts (prevents re-collection)
        self.player_to_heal = None # Store the player who initiated the collection
        
        self.frames_current_set = self.frames_closed # Start with closed frames
        self.image = self.frames_current_set[0]
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.pos = pygame.math.Vector2(x, y) # Store position if needed later

        self.current_frame_index = 0
        self.animation_timer = pygame.time.get_ticks() # For general animation frame timing
        self.time_opened_start = 0 # Timestamp when the chest becomes fully 'opened'
        self.fade_alpha = 255 # For fade-out effect

        if not self._valid_init: # If closed frames failed during init
             self.image = self.frames_closed[0] # Ensure it uses the placeholder
             self.rect = self.image.get_rect(midbottom=(x, y))


    def _create_placeholder_surface(self, color, text="Err"):
        surf = pygame.Surface((30, 30)).convert_alpha()
        surf.fill(color)
        pygame.draw.rect(surf, C.BLACK, surf.get_rect(), 1)
        try: 
            font = pygame.font.Font(None, 18)
            text_surf = font.render(text, True, C.BLACK)
            surf.blit(text_surf, text_surf.get_rect(center=surf.get_rect().center))
        except: pass # Ignore if font fails (e.g., pygame.font not init in a test)
        return surf

    def update(self, dt): # dt is delta time, not directly used here as timing is tick-based
        now = pygame.time.get_ticks()

        if self.state == 'killed':
            return

        # --- Animation Handling ---
        anim_speed_ms = C.ANIM_FRAME_DURATION
        if self.state == 'opening':
            anim_speed_ms *= 0.7 # Example: open animation is faster

        if now - self.animation_timer > anim_speed_ms:
            self.animation_timer = now
            self.current_frame_index += 1
            
            if self.current_frame_index >= len(self.frames_current_set):
                if self.state == 'opening': # Finished opening animation
                    self.current_frame_index = len(self.frames_current_set) - 1 # Stay on last open frame
                    self.state = 'opened'
                    self.time_opened_start = now # Record when it became fully opened
                    debug("Chest state changed to: opened")
                elif self.state == 'closed': # Loop closed animation
                    self.current_frame_index = 0
                # 'opened' state: Stays on last frame of open animation until timer elapses.
                # 'fading' state: Handles its own image alpha, not frame looping for open animation.
            
            # Update image if not fading (fading handles its own alpha)
            if self.state != 'fading':
                if self.frames_current_set and 0 <= self.current_frame_index < len(self.frames_current_set):
                    old_midbottom = self.rect.midbottom
                    self.image = self.frames_current_set[self.current_frame_index]
                    self.rect = self.image.get_rect(midbottom=old_midbottom)

        # --- State Transitions based on Time ---
        if self.state == 'opened':
            if now - self.time_opened_start >= C.CHEST_STAY_OPEN_DURATION_MS:
                self.state = 'fading'
                self.fade_alpha = 255 # Reset alpha for fade start
                # animation_timer will be used as fade_start_time effectively
                self.animation_timer = now # Use general animation timer to mark start of fade
                debug("Chest state changed to: fading")
        
        elif self.state == 'fading':
            elapsed_fade_time = now - self.animation_timer # time since fade started
            fade_progress = min(1.0, elapsed_fade_time / C.CHEST_FADE_OUT_DURATION_MS)
            self.fade_alpha = int(255 * (1.0 - fade_progress))
            
            # Ensure we use an "open" frame for fading
            if self.frames_open and self.frames_open[-1]: # Use last frame of open anim
                base_image = self.frames_open[-1] 
                self.image = base_image.copy() 
                self.image.set_alpha(max(0, self.fade_alpha))
            # Rect doesn't need to change during fade, only alpha

            if self.fade_alpha <= 0:
                debug("Chest fully faded out.")
                if self.player_to_heal and hasattr(self.player_to_heal, 'heal_to_full'):
                    info(f"Player {getattr(self.player_to_heal, 'player_id', 'Unknown')} healed by chest after fade.")
                    self.player_to_heal.heal_to_full()
                self.state = 'killed'
                self.kill() # Remove sprite from all groups

    def collect(self, player):
        """ Action when the player collects the chest. Triggers the opening sequence. """
        if self.is_collected_flag_internal or not self._valid_init or self.state != 'closed':
            # Already collected, invalid, or not in a state to be collected
            return

        info(f"Player {getattr(player, 'player_id', 'Unknown')} interacted with chest. State changing to 'opening'.")
        self.is_collected_flag_internal = True
        self.player_to_heal = player # Store player for healing later
        
        self.state = 'opening'
        self.frames_current_set = self.frames_open # Switch to open animation frames
        self.current_frame_index = 0 # Start animation from the first frame
        self.animation_timer = pygame.time.get_ticks() # Reset timer for the new animation
        # self.time_opened_start will be set when 'opening' animation finishes and state becomes 'opened'

        # Update image to the first frame of the 'opening' animation immediately
        if self.frames_current_set and self.frames_current_set[0]:
            old_midbottom = self.rect.midbottom
            self.image = self.frames_current_set[0]
            self.rect = self.image.get_rect(midbottom=old_midbottom)
        else:
            warning("Chest: Collect called, but 'open' frames are invalid. Chest might not animate correctly.")

########## END OF FILE: items.py ##########