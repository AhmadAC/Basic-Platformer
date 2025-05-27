#################### START OF FILE: editor\editor_logging.py ####################

# editor/editor_logging.py
# -*- coding: utf-8 -*-
"""
Centralized logging setup for the Platformer Level Editor.
Allows enabling/disabling file logging and console logging.
Version 2.0.1 (Minor refinement for base directory)
"""
import logging
import os
import traceback
from typing import Optional

# --- USER CONFIGURABLE LOGGING SETTINGS ---
ENABLE_FILE_LOGGING = True  
ENABLE_CONSOLE_DEBUG_LOGGING = True 

# --- Constants ---
LOG_DIRECTORY_NAME = 'logs' # This will be created within the script's execution context (e.g., editor/logs)
LOG_FILE_NAME = 'editor_debug.log'

# --- Global Logger Variable ---
logger: Optional[logging.Logger] = None

def setup_logging(script_main_dir: Optional[str] = None) -> logging.Logger:
    """
    Configures the root logger for the application.

    Args:
        script_main_dir (Optional[str]): The directory of the main script (e.g., editor.py).
                                         If None, it defaults to the directory of this logging script.
                                         This is where the 'logs' folder will be attempted.

    Returns:
        logging.Logger: The configured logger instance.
    """
    global logger 

    if logger is not None and logger.hasHandlers(): # Avoid reconfiguring if already done
        # This can happen if setup_logging is called multiple times inadvertently.
        # print("Logger already configured. Skipping reconfiguration.")
        return logger

    # Determine base directory for logs
    if script_main_dir:
        base_dir = script_main_dir
    else:
        # If this script is in 'editor/editor_logging.py', base_dir will be 'editor'
        base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()


    log_file_path = "Not determined" 

    # Remove any existing handlers from the root logger
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close() # Close handler before removing

    log_level = logging.DEBUG # Base level for root logger, handlers will filter
    
    handlers_to_add = []
    log_to_file_successful = False

    if ENABLE_FILE_LOGGING:
        try:
            # Create 'logs' directory relative to base_dir (e.g., editor/logs)
            logs_dir_path = os.path.join(base_dir, LOG_DIRECTORY_NAME)
            if not os.path.exists(logs_dir_path):
                print(f"Attempting to create logs directory: {logs_dir_path}")
                os.makedirs(logs_dir_path, exist_ok=True) # exist_ok=True is helpful
                print(f"Logs directory created (or already existed at {logs_dir_path}).")
            else:
                print(f"Logs directory already exists at: {logs_dir_path}")

            log_file_path = os.path.join(logs_dir_path, LOG_FILE_NAME)
            print(f"Attempting to configure file logging to: {log_file_path}")
            
            file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG) 
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

    console_handler = logging.StreamHandler() 
    console_formatter = logging.Formatter('CONSOLE: %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    if log_to_file_successful and not ENABLE_CONSOLE_DEBUG_LOGGING:
        console_handler.setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.DEBUG if ENABLE_CONSOLE_DEBUG_LOGGING else logging.INFO)
        
    handlers_to_add.append(console_handler)

    logging.basicConfig(
        level=log_level, 
        handlers=handlers_to_add
    )

    logger = logging.getLogger("PlatformerEditor") 
    logger.propagate = False # Prevent messages from going to the root logger if it also has handlers

    if log_to_file_successful:
        logger.info("Logging initialized. File logging is ON.")
    else:
        logger.info("Logging initialized. File logging is OFF or failed. Using console logging.")
    
    if ENABLE_CONSOLE_DEBUG_LOGGING or not log_to_file_successful: # If file logging failed, console debug should be on
        logger.info("Console DEBUG logging is ON (or file logging failed).")
    else:
        logger.info("Console DEBUG logging is OFF (INFO and above will still show on console).")
        
    return logger

#################### END OF FILE: editor\editor_logging.py ####################