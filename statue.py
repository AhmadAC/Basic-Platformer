########## START OF FILE: statue.py ##########
# statue.py
# -*- coding: utf-8 -*-
"""
# version 1.0.1
Defines the Statue class, an immobile object that an enemy can turn into.
It can be smashed and will then disappear.
"""
import pygame
import os
import constants as C
from assets import load_gif_frames, resource_path

try:
    from logger import debug, info
except ImportError:
    def debug(msg): print(f"DEBUG_STATUE: {msg}")
    def info(msg): print(f"INFO_STATUE: {msg}")

class Statue(pygame.sprite.Sprite):
    def __init__(self, center_x, center_y, statue_id=None):
        super().__init__()
        self.statue_id = statue_id if statue_id is not None else id(self) # For potential network sync

        # Load shared stone assets
        stone_asset_folder = os.path.join('characters', 'Stone')
        
        # Static stone image
        stone_png_path = resource_path(os.path.join(stone_asset_folder, '__Stone.png'))
        self.stone_image_frames = load_gif_frames(stone_png_path) # load_gif_frames handles single PNGs
        if not self.stone_image_frames or (len(self.stone_image_frames) == 1 and self.stone_image_frames[0].get_size() == (30,40) and self.stone_image_frames[0].get_at((0,0)) == C.RED):
            debug(f"Statue Error: Failed to load __Stone.png from '{stone_png_path}'. Using placeholder.")
            self.image = self._create_placeholder_surface(C.GRAY, "Stone")
            self.stone_image_frames = [self.image]
        else:
            self.image = self.stone_image_frames[0]

        # Smashed stone animation
        smashed_gif_path = resource_path(os.path.join(stone_asset_folder, '__StoneSmashed.gif'))
        self.smashed_frames = load_gif_frames(smashed_gif_path)
        if not self.smashed_frames or (len(self.smashed_frames) == 1 and self.smashed_frames[0].get_size() == (30,40) and self.smashed_frames[0].get_at((0,0)) == C.RED):
            debug(f"Statue Error: Failed to load __StoneSmashed.gif from '{smashed_gif_path}'. Using placeholder.")
            self.smashed_frames = [self._create_placeholder_surface(C.DARK_GRAY, "Smashed")]
        
        self.rect = self.image.get_rect(center=(center_x, center_y))
        self.pos = pygame.math.Vector2(self.rect.center) # Store center position

        self.is_smashed = False
        self.smashed_timer_start = 0
        self.current_frame_index = 0
        self.last_anim_update = pygame.time.get_ticks()
        self._valid_init = True # Assume valid unless assets truly fail catastrophically

        # Statues are solid and don't move
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, 0)
        self.is_dead = False # For game logic, a statue isn't "dead" in the same way an enemy is until it's gone
        self.death_animation_finished = False # Used by smashed animation timer

    def _create_placeholder_surface(self, color, text="Err"):
        # Use a somewhat generic size, actual size will come from loaded image.
        surf = pygame.Surface((C.TILE_SIZE, C.TILE_SIZE * 1.5)).convert_alpha() 
        surf.fill(color)
        pygame.draw.rect(surf, C.BLACK, surf.get_rect(), 1)
        try: 
            font = pygame.font.Font(None, 18)
            text_surf = font.render(text, True, C.BLACK)
            surf.blit(text_surf, text_surf.get_rect(center=surf.get_rect().center))
        except: pass 
        return surf

    def smash(self):
        if not self.is_smashed:
            info(f"Statue {self.statue_id} at {self.rect.center} is being smashed.")
            self.is_smashed = True
            self.smashed_timer_start = pygame.time.get_ticks()
            self.current_frame_index = 0
            self.last_anim_update = self.smashed_timer_start # Reset anim timer for smashed animation
            if self.smashed_frames:
                self.image = self.smashed_frames[0]
                # Important: Re-center the rect for the new animation if dimensions differ
                old_center = self.rect.center
                self.rect = self.image.get_rect(center=old_center)
                self.pos = pygame.math.Vector2(self.rect.center)


    def take_damage(self, damage_amount): # Statues are damaged by being smashed
        if not self.is_smashed:
            self.smash()

    def update(self, dt_sec=0): # dt_sec might not be used if animation is tick-based
        now = pygame.time.get_ticks()
        if self.is_smashed:
            if now - self.smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                info(f"Statue {self.statue_id} smashed duration ended. Killing.")
                self.kill() # Remove from all sprite groups
                return

            # Animate smashed stone
            if self.smashed_frames and len(self.smashed_frames) > 1: # Only animate if there's more than one frame
                anim_speed = C.ANIM_FRAME_DURATION 
                if now - self.last_anim_update > anim_speed:
                    self.last_anim_update = now
                    self.current_frame_index += 1
                    if self.current_frame_index >= len(self.smashed_frames):
                        self.current_frame_index = len(self.smashed_frames) - 1 # Stay on last frame
                    
                    old_center = self.rect.center
                    self.image = self.smashed_frames[self.current_frame_index]
                    self.rect = self.image.get_rect(center=old_center)
                    self.pos = pygame.math.Vector2(self.rect.center)
        else:
            # Static stone image
            if self.stone_image_frames:
                 self.image = self.stone_image_frames[0]
                 # Ensure rect matches in case it was somehow changed
                 old_center = self.rect.center
                 self.rect = self.image.get_rect(center=old_center)
                 self.pos = pygame.math.Vector2(self.rect.center)


    def get_network_data(self):
        return {
            'id': self.statue_id,
            'type': 'Statue', # To identify the object type on the client
            'pos': (self.pos.x, self.pos.y),
            'is_smashed': self.is_smashed,
            'smashed_timer_start': self.smashed_timer_start,
            'current_frame_index': self.current_frame_index, # For smashed animation sync
            # No need to send image data, client loads from its assets
        }

    def set_network_data(self, data):
        if 'pos' in data:
            self.pos.x, self.pos.y = data['pos']
            self.rect.center = round(self.pos.x), round(self.pos.y)
        
        new_is_smashed = data.get('is_smashed', self.is_smashed)
        if new_is_smashed and not self.is_smashed: # Server says it's smashed, but client thinks not
            self.is_smashed = True
            self.smashed_timer_start = data.get('smashed_timer_start', pygame.time.get_ticks())
            self.current_frame_index = data.get('current_frame_index', 0)
            self.last_anim_update = pygame.time.get_ticks() # Sync anim timer
            if self.smashed_frames and self.smashed_frames[self.current_frame_index % len(self.smashed_frames)]:
                self.image = self.smashed_frames[self.current_frame_index % len(self.smashed_frames)]
                self.rect = self.image.get_rect(center=(round(self.pos.x), round(self.pos.y)))
        elif not new_is_smashed and self.is_smashed: # Server says not smashed (e.g. reset), but client thinks so
            self.is_smashed = False
            if self.stone_image_frames:
                self.image = self.stone_image_frames[0]
                self.rect = self.image.get_rect(center=(round(self.pos.x), round(self.pos.y)))

        if self.is_smashed: # If it is indeed smashed, sync frame and timer
            self.smashed_timer_start = data.get('smashed_timer_start', self.smashed_timer_start)
            self.current_frame_index = data.get('current_frame_index', self.current_frame_index)
            # Visual update will happen in self.update()
            if self.smashed_frames and self.smashed_frames[self.current_frame_index % len(self.smashed_frames)]:
                 self.image = self.smashed_frames[self.current_frame_index % len(self.smashed_frames)]
                 self.rect = self.image.get_rect(center=(round(self.pos.x), round(self.pos.y)))


    # Add a property to make Statues behave like platforms for collision
    @property
    def platform_type(self):
        return "stone_wall" # Can be used for specific collision responses if needed

########## END OF FILE: statue.py ##########