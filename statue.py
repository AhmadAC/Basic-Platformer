# statue.py
# -*- coding: utf-8 -*-
"""
Defines the Statue class, an immobile object that can be smashed.
It can represent a generic stone statue in the level.
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
    def __init__(self, center_x, center_y, statue_id=None, 
                 initial_image_path=None, smashed_anim_path=None):
        super().__init__()
        self.statue_id = statue_id if statue_id is not None else id(self)
        self._valid_init = True

        # Determine asset paths
        stone_asset_folder = os.path.join('characters', 'Stone')
        # Use provided paths if available, otherwise default
        default_initial_image_path = initial_image_path if initial_image_path else os.path.join(stone_asset_folder, '__Stone.png')
        default_smashed_anim_path = smashed_anim_path if smashed_anim_path else os.path.join(stone_asset_folder, '__StoneSmashed.gif')
        # Example: Could use StoneSmashed_c.gif if needed:
        # default_smashed_anim_path = os.path.join(stone_asset_folder, 'StoneSmashed_c.gif')


        # Load initial static image
        full_initial_path = resource_path(default_initial_image_path)
        self.initial_image_frames = load_gif_frames(full_initial_path)
        if not self.initial_image_frames or self._is_placeholder(self.initial_image_frames[0]):
            debug(f"Statue Error: Failed to load initial image from '{full_initial_path}'. Using placeholder.")
            self.image = self._create_placeholder_surface(C.GRAY, "StatueImg")
            self.initial_image_frames = [self.image]
            # self._valid_init = False # Decide if this is critical enough to invalidate
        else:
            self.image = self.initial_image_frames[0]

        # Load smashed animation
        full_smashed_path = resource_path(default_smashed_anim_path)
        self.smashed_frames = load_gif_frames(full_smashed_path)
        if not self.smashed_frames or self._is_placeholder(self.smashed_frames[0]):
            debug(f"Statue Error: Failed to load smashed animation from '{full_smashed_path}'. Using placeholder.")
            self.smashed_frames = [self._create_placeholder_surface(C.DARK_GRAY, "SmashedStat")]
        
        self.rect = self.image.get_rect(center=(center_x, center_y))
        self.pos = pygame.math.Vector2(self.rect.center)

        self.is_smashed = False
        self.smashed_timer_start = 0
        self.current_frame_index = 0
        self.last_anim_update = pygame.time.get_ticks()
        
        self.is_dead = False 
        self.death_animation_finished = False

    def _is_placeholder(self, frame_surface):
        if frame_surface.get_size() == (30,40):
            color_at_origin = frame_surface.get_at((0,0))
            if color_at_origin == C.RED or color_at_origin == C.BLUE:
                return True
        return False

    def _create_placeholder_surface(self, color, text="Err"):
        height = self.initial_image_frames[0].get_height() if self.initial_image_frames and self.initial_image_frames[0] else int(C.TILE_SIZE * 1.5)
        width = self.initial_image_frames[0].get_width() if self.initial_image_frames and self.initial_image_frames[0] else C.TILE_SIZE
        surf = pygame.Surface((width, height)).convert_alpha() 
        surf.fill(color)
        pygame.draw.rect(surf, C.BLACK, surf.get_rect(), 1)
        try: 
            font = pygame.font.Font(None, 18)
            text_surf = font.render(text, True, C.BLACK)
            surf.blit(text_surf, text_surf.get_rect(center=surf.get_rect().center))
        except: pass 
        return surf

    def smash(self):
        if not self.is_smashed and self._valid_init:
            info(f"Statue {self.statue_id} at {self.rect.center} is being smashed.")
            self.is_smashed = True
            self.smashed_timer_start = pygame.time.get_ticks()
            self.current_frame_index = 0
            self.last_anim_update = self.smashed_timer_start
            if self.smashed_frames:
                self.image = self.smashed_frames[0]
                old_center = self.rect.center
                self.rect = self.image.get_rect(center=old_center)
                self.pos = pygame.math.Vector2(self.rect.center)

    def take_damage(self, damage_amount): # Any damage smashes it
        if not self.is_smashed and self._valid_init:
            self.smash()

    def update(self, dt_sec=0):
        if not self._valid_init: return
        now = pygame.time.get_ticks()

        if self.is_smashed:
            if now - self.smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                if not self.death_animation_finished:
                    info(f"Statue {self.statue_id} smashed duration ended. Killing.")
                    self.death_animation_finished = True # Mark that the logical "death" (disappearance) should occur
                self.is_dead = True # Mark as logically dead
                self.kill() 
                return

            if self.smashed_frames and len(self.smashed_frames) > 1:
                anim_speed = C.ANIM_FRAME_DURATION 
                if now - self.last_anim_update > anim_speed:
                    self.last_anim_update = now
                    self.current_frame_index += 1
                    if self.current_frame_index >= len(self.smashed_frames):
                        self.current_frame_index = len(self.smashed_frames) - 1 
                        # self.death_animation_finished = True # Visual animation done, but object persists until timer
                    
                    old_center = self.rect.center
                    self.image = self.smashed_frames[self.current_frame_index]
                    self.rect = self.image.get_rect(center=old_center)
                    self.pos = pygame.math.Vector2(self.rect.center)
        else: 
            if self.initial_image_frames:
                 self.image = self.initial_image_frames[0]
                 old_center = self.rect.center
                 self.rect = self.image.get_rect(center=old_center)
                 self.pos = pygame.math.Vector2(self.rect.center)

    def get_network_data(self):
        return {
            'id': self.statue_id, 'type': 'Statue',
            'pos': (self.pos.x, self.pos.y), 'is_smashed': self.is_smashed,
            'smashed_timer_start': self.smashed_timer_start,
            'current_frame_index': self.current_frame_index,
            '_valid_init': self._valid_init,
            'is_dead': self.is_dead, # Important for client to know if it should be removed
            'death_animation_finished': self.death_animation_finished
        }

    def set_network_data(self, data):
        self._valid_init = data.get('_valid_init', self._valid_init)
        if not self._valid_init:
            if self.alive(): self.kill()
            return

        if 'pos' in data:
            self.pos.x, self.pos.y = data['pos']
            self.rect.center = round(self.pos.x), round(self.pos.y)
        
        new_is_smashed = data.get('is_smashed', self.is_smashed)
        if new_is_smashed != self.is_smashed:
            self.is_smashed = new_is_smashed
            if self.is_smashed:
                self.smashed_timer_start = data.get('smashed_timer_start', pygame.time.get_ticks())
                self.current_frame_index = data.get('current_frame_index', 0)
                self.last_anim_update = pygame.time.get_ticks()
            # Image update will happen in update() or below
            
        self.is_dead = data.get('is_dead', self.is_dead)
        self.death_animation_finished = data.get('death_animation_finished', self.death_animation_finished)

        if self.is_smashed:
            self.smashed_timer_start = data.get('smashed_timer_start', self.smashed_timer_start)
            self.current_frame_index = data.get('current_frame_index', self.current_frame_index)
            if self.smashed_frames and 0 <= self.current_frame_index < len(self.smashed_frames):
                self.image = self.smashed_frames[self.current_frame_index]
            elif self.smashed_frames: # Default to first frame if index is bad
                self.image = self.smashed_frames[0]
            self.rect = self.image.get_rect(center=(round(self.pos.x), round(self.pos.y)))
        else:
            if self.initial_image_frames:
                 self.image = self.initial_image_frames[0]
                 self.rect = self.image.get_rect(center=(round(self.pos.x), round(self.pos.y)))
        
        if self.is_dead and self.alive(): # If server says it's dead (e.g., fully faded)
            self.kill()


    @property
    def platform_type(self):
        return "stone_wall" if not self.is_smashed else "smashed_debris" # Debris might be non-collidable