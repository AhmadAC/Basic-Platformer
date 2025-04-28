# -*- coding: utf-8 -*-
"""
Functions for drawing User Interface elements like health bars.
"""
import pygame
from constants import GREEN, RED, DARK_GRAY, BLACK, WHITE # Import colors

def draw_health_bar(surface, x, y, width, height, current_hp, max_hp):
    """ Draws a health bar at the given position with color transition. """
    if max_hp <= 0: return # Avoid division by zero and drawing invalid bar

    # Clamp values to prevent visual errors
    current_hp = max(0, current_hp)
    width = max(1, width)
    height = max(1, height)

    # Calculate health ratio
    hp_ratio = min(1, current_hp / max_hp) # Clamp between 0 and 1

    # Determine color based on health ratio (Green -> Yellow -> Red)
    try:
        # Pygame Color lerp is efficient if available
        health_color = pygame.Color(RED).lerp(GREEN, hp_ratio)
    except AttributeError:
        # Manual lerp fallback for older Pygame versions
        r = int(RED[0] * (1 - hp_ratio) + GREEN[0] * hp_ratio)
        g = int(RED[1] * (1 - hp_ratio) + GREEN[1] * hp_ratio)
        b = int(RED[2] * (1 - hp_ratio) + GREEN[2] * hp_ratio)
        health_color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    # Calculate width of the health part
    health_fill_width = int(width * hp_ratio)

    # Draw the background bar (dark gray)
    background_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, DARK_GRAY, background_rect)

    # Draw the health fill only if there's width to draw
    if health_fill_width > 0:
        health_rect = pygame.Rect(x, y, health_fill_width, height)
        pygame.draw.rect(surface, health_color, health_rect)

    # Draw a border (optional, black)

# -*- coding: utf-8 -*-
"""
Functions for drawing User Interface elements like health bars.
"""
import pygame
from constants import GREEN, RED, DARK_GRAY, BLACK, WHITE # Import colors

def draw_health_bar(surface, x, y, width, height, current_hp, max_hp):
    """ Draws a health bar at the given position with color transition. """
    if max_hp <= 0: return # Avoid division by zero and drawing invalid bar

    # Clamp values to prevent visual errors
    current_hp = max(0, current_hp)
    width = max(1, width)
    height = max(1, height)

    # Calculate health ratio
    hp_ratio = min(1, current_hp / max_hp) # Clamp between 0 and 1

    # Determine color based on health ratio (Green -> Yellow -> Red)
    try:
        # Pygame Color lerp is efficient if available
        health_color = pygame.Color(RED).lerp(GREEN, hp_ratio)
    except AttributeError:
        # Manual lerp fallback for older Pygame versions
        r = int(RED[0] * (1 - hp_ratio) + GREEN[0] * hp_ratio)
        g = int(RED[1] * (1 - hp_ratio) + GREEN[1] * hp_ratio)
        b = int(RED[2] * (1 - hp_ratio) + GREEN[2] * hp_ratio)
        health_color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    # Calculate width of the health part
    health_fill_width = int(width * hp_ratio)

    # Draw the background bar (dark gray)
    background_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, DARK_GRAY, background_rect)

    # Draw the health fill only if there's width to draw
    if health_fill_width > 0:
        health_rect = pygame.Rect(x, y, health_fill_width, height)
        pygame.draw.rect(surface, health_color, health_rect)

    # Draw a border (optional, black)
    pygame.draw.rect(surface, BLACK, background_rect, 1) # 1 pixel border