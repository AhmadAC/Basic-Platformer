########## START OF FILE: joystick_handler.py ##########
# joystick_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.1
Handles joystick detection and basic information retrieval.
"""
import pygame

joysticks = [] # List to store initialized joystick objects

def init_joysticks():
    """Initializes the Pygame joystick system and detects connected joysticks."""
    global joysticks
    pygame.joystick.init() # Initialize the joystick subsystem
    joysticks = []
    count = pygame.joystick.get_count()
    print(f"JOY_HANDLER: Found {count} joystick(s).")
    for i in range(count):
        try:
            joystick = pygame.joystick.Joystick(i)
            joystick.init() # Initialize each joystick
            joysticks.append(joystick)
            print(f"JOY_HANDLER: Initialized Joystick {i}: {joystick.get_name()} with {joystick.get_numaxes()} axes, {joystick.get_numbuttons()} buttons, {joystick.get_numhats()} hats.")
        except pygame.error as e:
            print(f"JOY_HANDLER: Error initializing joystick {i}: {e}")
    if not joysticks and count > 0:
        print("JOY_HANDLER: Pygame reported joysticks, but none could be initialized.")


def get_joystick_count():
    """Returns the number of successfully initialized joysticks."""
    return len(joysticks)

def get_joystick_name(joystick_id):
    """Returns the name of the joystick with the given ID."""
    if 0 <= joystick_id < len(joysticks):
        try:
            return joysticks[joystick_id].get_name()
        except pygame.error: # Handle if joystick was disconnected or init failed after list populated
            return f"Joystick {joystick_id} (Error)"
    return f"Joystick {joystick_id} (Not Found)"

def get_joystick_instance(joystick_id):
    """Returns the Pygame Joystick object for the given ID, or None."""
    if 0 <= joystick_id < len(joysticks):
        return joysticks[joystick_id]
    return None

def quit_joysticks():
    """Uninitializes the joystick subsystem."""
    global joysticks
    # Joysticks are uninitialized automatically by pygame.joystick.quit()
    # for joy in joysticks:
    # if joy.get_init(): # Check if it was initialized
    # joy.quit()
    pygame.joystick.quit()
    joysticks = []
    print("JOY_HANDLER: Joystick subsystem uninitialized.")

########## END OF FILE: joystick_handler.py ##########