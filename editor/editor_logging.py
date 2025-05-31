# editor/editor_logging.py
# -*- coding: utf-8 -*-
"""
Centralized logging setup specifically for the Platformer Level Editor.
Allows enabling/disabling file logging and console logging for the editor.
This setup is intended to be independent or complementary to any main game logger.
Version 2.0.2 (Clarified script_main_dir, robust init)
"""
import logging
import os
import traceback
from typing import Optional

# --- USER CONFIGURABLE LOGGING SETTINGS ---
# These settings control the editor's own logging behavior.
ENABLE_EDITOR_FILE_LOGGING = True
EDITOR_FILE_LOG_LEVEL = logging.DEBUG  # e.g., DEBUG, INFO, WARNING
ENABLE_EDITOR_CONSOLE_LOGGING = True
# Level for console if file logging IS active and successful
EDITOR_CONSOLE_LEVEL_WHEN_FILE_ACTIVE = logging.INFO
# Level for console if file logging IS NOT active or FAILED
EDITOR_CONSOLE_LEVEL_WHEN_FILE_FAILED = logging.DEBUG
# If file logging fails, should console switch to DEBUG automatically?
EDITOR_FORCE_CONSOLE_DEBUG_ON_FILE_FAIL = True

# --- Constants ---
# Log directory will be created relative to the script_main_dir passed to setup_logging,
# or relative to this file's directory if script_main_dir is None.
EDITOR_LOG_DIRECTORY_NAME = 'logs_editor' # Distinct name if coexisting with game logs
EDITOR_LOG_FILE_NAME = 'editor_session_debug.log'

# --- Global Logger Variable for the Editor ---
_editor_logger_instance: Optional[logging.Logger] = None

def setup_editor_logging(script_main_dir: Optional[str] = None) -> logging.Logger:
    """
    Configures a dedicated logger for the editor.

    Args:
        script_main_dir (Optional[str]): The directory considered as the root for
                                         placing the editor's log folder (e.g., editor/logs_editor).
                                         If None, it defaults to this script's directory.

    Returns:
        logging.Logger: The configured logger instance for the editor.
    """
    global _editor_logger_instance

    if _editor_logger_instance is not None and _editor_logger_instance.hasHandlers():
        # Logger already configured, return existing instance.
        # This might happen if setup is called multiple times.
        return _editor_logger_instance

    # Determine base directory for editor logs
    if script_main_dir and os.path.isdir(script_main_dir):
        base_dir_for_logs = script_main_dir
    else:
        # If this script is in 'editor/editor_logging.py', base_dir will be 'editor'
        base_dir_for_logs = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()

    # Create the specific logger instance for the editor
    _editor_logger_instance = logging.getLogger("PlatformerEditorLogger") # Unique name
    _editor_logger_instance.setLevel(logging.DEBUG) # Process all messages at DEBUG or higher

    # Clear any existing handlers from THIS logger instance to prevent duplication
    for handler in list(_editor_logger_instance.handlers):
        _editor_logger_instance.removeHandler(handler)
        handler.close()

    handlers_to_add_editor: List[logging.Handler] = []
    file_logging_for_editor_successful = False
    log_file_path_editor = "Not determined (editor logging)"

    if ENABLE_EDITOR_FILE_LOGGING:
        try:
            logs_dir_path_editor = os.path.join(base_dir_for_logs, EDITOR_LOG_DIRECTORY_NAME)
            if not os.path.exists(logs_dir_path_editor):
                print(f"EDITOR_LOGGING: Attempting to create editor logs directory: {logs_dir_path_editor}")
                os.makedirs(logs_dir_path_editor, exist_ok=True)
            
            log_file_path_editor = os.path.join(logs_dir_path_editor, EDITOR_LOG_FILE_NAME)
            
            file_handler_editor = logging.FileHandler(log_file_path_editor, mode='w', encoding='utf-8')
            file_formatter_editor = logging.Formatter(
                "[%(asctime)s.%(msecs)03d] EDITOR %(levelname)-7s %(filename)s:%(lineno)d (%(funcName)s): %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler_editor.setFormatter(file_formatter_editor)
            file_handler_editor.setLevel(EDITOR_FILE_LOG_LEVEL)
            handlers_to_add_editor.append(file_handler_editor)
            file_logging_for_editor_successful = True
            print(f"EDITOR_LOGGING: File logging configured. Log file: {log_file_path_editor}")
        except Exception as e_log_file_editor:
            # Use basic print for critical setup errors as logger might not be fully working
            sys.stderr.write(f"EDITOR_LOGGING CRITICAL ERROR: Failed file logging setup: {e_log_file_editor}\n")
            sys.stderr.write(f"  Traceback: {traceback.format_exc()}\n")
            sys.stderr.write(f"  Attempted log file path: {log_file_path_editor}\n")
            file_logging_for_editor_successful = False

    if ENABLE_EDITOR_CONSOLE_LOGGING:
        console_handler_editor = logging.StreamHandler(sys.stdout)
        console_formatter_editor = logging.Formatter("EDITOR CONSOLE %(levelname)-7s: %(message)s (%(filename)s:%(lineno)d)")
        console_handler_editor.setFormatter(console_formatter_editor)

        if file_logging_for_editor_successful:
            console_handler_editor.setLevel(EDITOR_CONSOLE_LEVEL_WHEN_FILE_ACTIVE)
        else:
            console_handler_editor.setLevel(logging.DEBUG if EDITOR_FORCE_CONSOLE_DEBUG_ON_FILE_FAIL else EDITOR_CONSOLE_LEVEL_WHEN_FILE_FAILED)
        handlers_to_add_editor.append(console_handler_editor)

    if not handlers_to_add_editor: # If both file and console are off or failed
        _editor_logger_instance.addHandler(logging.NullHandler()) # Ensure it's silenced
        print("EDITOR_LOGGING: All editor logging outputs are disabled.")
    else:
        for handler_to_add in handlers_to_add_editor:
            _editor_logger_instance.addHandler(handler_to_add)
    
    _editor_logger_instance.propagate = False # Prevent messages from going to the root logger

    # Log initial status using the newly configured logger
    if file_logging_for_editor_successful:
        _editor_logger_instance.info(f"Editor file logging initialized. Level: {logging.getLevelName(EDITOR_FILE_LOG_LEVEL)}. Output: {log_file_path_editor}")
    else:
        _editor_logger_instance.warning(f"Editor file logging FAILED or DISABLED. Attempted path: {log_file_path_editor}")
    
    if ENABLE_EDITOR_CONSOLE_LOGGING and any(isinstance(h, logging.StreamHandler) for h in _editor_logger_instance.handlers):
        console_handler_level_name = logging.getLevelName(EDITOR_CONSOLE_LEVEL_WHEN_FILE_ACTIVE if file_logging_for_editor_successful else (logging.DEBUG if EDITOR_FORCE_CONSOLE_DEBUG_ON_FILE_FAIL else EDITOR_CONSOLE_LEVEL_WHEN_FILE_FAILED))
        _editor_logger_instance.info(f"Editor console logging initialized. Level: {console_handler_level_name}.")
    elif ENABLE_EDITOR_CONSOLE_LOGGING: # This case means console was enabled but handler wasn't added (shouldn't happen)
         _editor_logger_instance.warning("Editor console logging was enabled but handler not added. Check setup.")

    return _editor_logger_instance


if __name__ == "__main__":
    print("--- Testing editor/editor_logging.py setup ---")
    # Test with script_main_dir = None (logs relative to this file's dir)
    print("\n--- Test 1: Default (script_main_dir=None) ---")
    logger1 = setup_editor_logging()
    logger1.debug("Editor Logger 1 - DEBUG message.")
    logger1.info("Editor Logger 1 - INFO message.")
    logger1.warning("Editor Logger 1 - WARNING message.")

    # Test with a specified script_main_dir (e.g., current working directory)
    # For this test, ensure the global _editor_logger_instance is reset.
    _editor_logger_instance = None # Reset global for re-initialization
    test_log_dir = os.path.join(os.getcwd(), "editor_test_logs")
    if not os.path.exists(test_log_dir):
        os.makedirs(test_log_dir)
    print(f"\n--- Test 2: Specified script_main_dir ('{test_log_dir}') ---")
    logger2 = setup_editor_logging(script_main_dir=test_log_dir)
    logger2.debug("Editor Logger 2 - DEBUG message (in specified dir).")
    logger2.info("Editor Logger 2 - INFO message (in specified dir).")

    print("\n--- Test Finished. Check console output and log files. ---")
    print(f"Expected log file for Test 1 should be near: {os.path.join(os.path.dirname(__file__), EDITOR_LOG_DIRECTORY_NAME, EDITOR_LOG_FILE_NAME)}")
    print(f"Expected log file for Test 2 should be in: {os.path.join(test_log_dir, EDITOR_LOG_DIRECTORY_NAME, EDITOR_LOG_FILE_NAME)}")