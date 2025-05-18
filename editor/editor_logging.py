# editor/editor_logging.py
# -*- coding: utf-8 -*-
"""
Centralized logging setup for the Platformer Level Editor.
Allows enabling/disabling file logging and console logging.
"""
import logging
import os
import traceback
from typing import Optional

# --- USER CONFIGURABLE LOGGING SETTINGS ---
ENABLE_FILE_LOGGING = True  # Set to False to disable writing logs to a file
ENABLE_CONSOLE_DEBUG_LOGGING = True # Set to False to disable DEBUG level messages to console (INFO and above will still show if file logging also fails)
# If ENABLE_FILE_LOGGING is False, console logging will be used as a fallback,
# respecting ENABLE_CONSOLE_DEBUG_LOGGING for DEBUG messages.

# --- Constants ---
LOG_DIRECTORY_NAME = 'logs'
LOG_FILE_NAME = 'editor_debug.log'

# --- Global Logger Variable ---
# This will be set by setup_logging() and can be imported by other modules.
logger: Optional[logging.Logger] = None

def setup_logging(script_main_dir: Optional[str] = None) -> logging.Logger:
    """
    Configures the root logger for the application.

    Args:
        script_main_dir (Optional[str]): The directory of the main script (e.g., editor.py).
                                         If None, it attempts to use the directory of this logging script.

    Returns:
        logging.Logger: The configured logger instance.
    """
    global logger # Allow modification of the global logger variable

    # Determine base directory for logs
    if script_main_dir:
        base_dir = script_main_dir
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of this logging script

    log_file_path = "Not determined" # Default for error messages

    # Remove any existing handlers from the root logger to avoid duplicate logs
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    log_level = logging.DEBUG if ENABLE_CONSOLE_DEBUG_LOGGING else logging.INFO
    
    handlers_to_add = []
    log_to_file_successful = False

    if ENABLE_FILE_LOGGING:
        try:
            logs_dir_path = os.path.join(base_dir, LOG_DIRECTORY_NAME)
            if not os.path.exists(logs_dir_path):
                print(f"Attempting to create logs directory: {logs_dir_path}")
                os.makedirs(logs_dir_path)
                print(f"Logs directory created (or already existed at {logs_dir_path}).")
            else:
                print(f"Logs directory already exists at: {logs_dir_path}")

            log_file_path = os.path.join(logs_dir_path, LOG_FILE_NAME)
            print(f"Attempting to configure file logging to: {log_file_path}")
            
            file_handler = logging.FileHandler(log_file_path, mode='w')
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG) # Always log DEBUG to file if file logging is on
            handlers_to_add.append(file_handler)
            log_to_file_successful = True
            print(f"File logging configured. Log file should be at: {log_file_path}")
        except Exception as e_log_file:
            print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(f"CRITICAL ERROR DURING FILE LOGGING SETUP: {e_log_file}")
            print(f"Traceback for file logging error:")
            traceback.print_exc()
            print(f"Log file might not be created. Attempted log file path was: {log_file_path}")
            print(f"Falling back to console logging only.")
            print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            log_to_file_successful = False

    # Always add a console handler, its level depends on settings
    console_handler = logging.StreamHandler() # Defaults to sys.stderr
    console_formatter = logging.Formatter('CONSOLE: %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    if log_to_file_successful and not ENABLE_CONSOLE_DEBUG_LOGGING:
        # If file logging is working and user wants less console verbosity, set console to INFO
        console_handler.setLevel(logging.INFO)
    else:
        # Otherwise (file logging off, or file logging failed, or console debug is on), set console by ENABLE_CONSOLE_DEBUG_LOGGING
        console_handler.setLevel(logging.DEBUG if ENABLE_CONSOLE_DEBUG_LOGGING else logging.INFO)
        
    handlers_to_add.append(console_handler)

    logging.basicConfig(
        level=logging.DEBUG, # Root logger set to DEBUG to allow handlers to filter
        handlers=handlers_to_add
    )

    logger = logging.getLogger("PlatformerEditor") # Get a named logger for the application

    if log_to_file_successful:
        logger.info("Logging initialized. File logging is ON.")
    else:
        logger.info("Logging initialized. File logging is OFF or failed. Using console logging.")
    
    if ENABLE_CONSOLE_DEBUG_LOGGING:
        logger.info("Console DEBUG logging is ON.")
    else:
        logger.info("Console DEBUG logging is OFF (INFO and above will still show on console if file logging is off/failed).")
        
    return logger

# Example of how to get the logger in other modules:
# from editor_logging import logger
# if logger:
# logger.info("This is an info message from another_module.py")