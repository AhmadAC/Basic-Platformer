# -*- coding: utf-8 -*-
"""
Functions for drawing User Interface elements like health bars and player HUDs.
"""
# version 1.00000.1
import pygame
import constants as C # Import constants with C. prefix

# --- Font Initialization (Initialize once) ---
# It's good practice to initialize fonts once, e.g., when the UI module is imported or in a setup function.
# For simplicity, we'll do it here. Handle font loading errors gracefully.
try:
    pygame.font.init() # Ensure the font module is initialized
    HUD_FONT_SIZE = 20
    HUD_FONT = pygame.font.Font(None, HUD_FONT_SIZE) # Use default system font
    # For a custom font: HUD_FONT = pygame.font.Font("path/to/your/font.ttf", HUD_FONT_SIZE)
except pygame.error as e:
    print(f"Warning: Could not initialize font: {e}. Using fallback.")
    HUD_FONT = None
except Exception as e: # Catch other potential errors during font loading
    print(f"Warning: An unexpected error occurred while initializing font: {e}. Using fallback.")
    HUD_FONT = None

if HUD_FONT is None: # Fallback if font loading failed
    try: # Try a very basic Pygame font if default failed
        HUD_FONT = pygame.font.SysFont("arial", HUD_FONT_SIZE) # Common system font
    except pygame.error: # If even SysFont fails
        print("Critical Warning: All font loading failed. Text HUD elements will not be drawn.")
        HUD_FONT = None # Ensure it's None so checks below work

# --- Existing Health Bar Function ---
def draw_health_bar(surface, x, y, width, height, current_hp, max_hp):
    """ Draws a health bar at the given position with color transition. """
    if max_hp <= 0: return

    current_hp = max(0, current_hp)
    width = max(1, width)
    height = max(1, height)
    hp_ratio = min(1, current_hp / max_hp)

    try:
        health_color = pygame.Color(C.RED).lerp(C.GREEN, hp_ratio)
    except AttributeError: # Manual lerp for older Pygame or if Color.lerp is missing
        r = int(C.RED[0] * (1 - hp_ratio) + C.GREEN[0] * hp_ratio)
        g = int(C.RED[1] * (1 - hp_ratio) + C.GREEN[1] * hp_ratio)
        b = int(C.RED[2] * (1 - hp_ratio) + C.GREEN[2] * hp_ratio)
        health_color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    background_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, C.DARK_GRAY, background_rect)

    health_fill_width = int(width * hp_ratio)
    if health_fill_width > 0:
        health_rect = pygame.Rect(x, y, health_fill_width, height)
        pygame.draw.rect(surface, health_color, health_rect)
    pygame.draw.rect(surface, C.BLACK, background_rect, 1)


# --- NEW: Player HUD Function ---
def draw_player_hud(surface, x, y, player, player_number):
    """
    Draws the Heads-Up Display for a given player.
    Includes player label and health bar.

    Args:
        surface (pygame.Surface): The surface to draw on.
        x (int): The top-left x-coordinate for the HUD.
        y (int): The top-left y-coordinate for the HUD.
        player (Player): The player object, expected to have 'current_health' and 'max_health'.
        player_number (int): The number of the player (e.g., 1 or 2).
    """
    if not player or not hasattr(player, 'current_health') or not hasattr(player, 'max_health'):
        # print(f"Warning: Invalid player object or missing health attributes for HUD P{player_number}.")
        return

    # --- Player Label ---
    label_text = f"P{player_number}"
    if HUD_FONT:
        try:
            label_surface = HUD_FONT.render(label_text, True, C.WHITE)
            surface.blit(label_surface, (x, y))
            label_height = label_surface.get_height()
        except pygame.error as e: # Catch errors during rendering (e.g. font not loaded)
            print(f"Warning: Could not render HUD label for P{player_number}: {e}")
            label_height = HUD_FONT_SIZE # Estimate height
        except Exception as e:
            print(f"Warning: Unexpected error rendering HUD label for P{player_number}: {e}")
            label_height = HUD_FONT_SIZE
    else: # No font loaded
        label_height = 0 # No label to draw, so no height offset for health bar

    # --- Health Bar ---
    # Position health bar below the label
    health_bar_x = x
    health_bar_y = y + label_height + 5  # Add some padding
    health_bar_width = C.HEALTH_BAR_WIDTH * 2 # Make it a bit wider for HUD
    health_bar_height = C.HEALTH_BAR_HEIGHT + 4 # Make it a bit taller for HUD

    draw_health_bar(surface, health_bar_x, health_bar_y,
                    health_bar_width, health_bar_height,
                    player.current_health, player.max_health)

    # --- Optional: Draw Health Value Text ---
    if HUD_FONT:
        try:
            health_text = f"{int(player.current_health)}/{int(player.max_health)}"
            health_text_surface = HUD_FONT.render(health_text, True, C.WHITE)
            # Position text next to or on the health bar
            text_x = health_bar_x + health_bar_width + 10
            text_y = health_bar_y + (health_bar_height - health_text_surface.get_height()) / 2 # Center vertically
            surface.blit(health_text_surface, (text_x, text_y))
        except pygame.error as e:
            print(f"Warning: Could not render HUD health text for P{player_number}: {e}")
        except Exception as e:
            print(f"Warning: Unexpected error rendering HUD health text for P{player_number}: {e}")


# Example of how you might call this in your main loop (for testing ui.py directly)
if __name__ == '__main__':
    pygame.init()
    if not pygame.font.get_init(): # Ensure font module is initialized if running directly
        pygame.font.init()
        if HUD_FONT is None: # Re-attempt basic font loading if it failed at module level
            try:
                HUD_FONT = pygame.font.SysFont("arial", 20)
            except:
                print("Main test: Font loading failed.")


    screen_width = 300
    screen_height = 200
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("UI Test")

    # Dummy player object for testing
    class DummyPlayer:
        def __init__(self, current_hp, max_hp):
            self.current_health = current_hp
            self.max_health = max_hp

    player1_dummy = DummyPlayer(80, 100)
    player2_dummy = DummyPlayer(50, C.PLAYER_MAX_HEALTH)


    running = True
    clock = pygame.time.Clock()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN: # Simple test to change health
                if event.key == pygame.K_1:
                    player1_dummy.current_health = max(0, player1_dummy.current_health -10)
                if event.key == pygame.K_2:
                    player2_dummy.current_health = max(0, player2_dummy.current_health -10)


        screen.fill(C.LIGHT_BLUE) # Background

        # Test draw_player_hud
        if HUD_FONT: # Only draw if font is available
            draw_player_hud(screen, 10, 10, player1_dummy, 1)
            draw_player_hud(screen, 10, 70, player2_dummy, 2)
        else:
            # Fallback: just draw health bars if no font
            draw_health_bar(screen, 10, 10, C.HEALTH_BAR_WIDTH * 2, C.HEALTH_BAR_HEIGHT + 4, player1_dummy.current_health, player1_dummy.max_health)
            draw_health_bar(screen, 10, 70, C.HEALTH_BAR_WIDTH * 2, C.HEALTH_BAR_HEIGHT + 4, player2_dummy.current_health, player2_dummy.max_health)


        pygame.display.flip()
        clock.tick(C.FPS)

    pygame.quit()