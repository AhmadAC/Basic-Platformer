#################### START OF FILE: logger.py ####################

# logger.py
# version 1.0.0.5 (Robust initialization, ensure logging functions are defined even on failure)

from typing import List, Dict, Tuple, Any, Optional
import logging
import os
import sys # For sys.stderr
import time
import math

# --- USER CONFIGURABLE LOGGING SETTINGS ---
LOGGING_ENABLED = True
ENABLE_FILE_LOGGING = True
FILE_LOG_LEVEL = logging.DEBUG
ENABLE_CONSOLE_LOGGING = True
CONSOLE_LEVEL_WHEN_FILE_ACTIVE = logging.WARNING
CONSOLE_LEVEL_WHEN_FILE_FAILED = logging.INFO
ENABLE_DEBUG_ON_CONSOLE_IF_FILE_FAILS = True
ENABLE_DETAILED_PHYSICS_LOGS = False
PHYSICS_LOG_INTERVAL_SEC = 0.5
# --- ---

_last_physics_log_time_by_player: Dict[str, float] = {}
LOG_FILENAME = "platformer_debug.log"
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILENAME)

_platformer_logger_instance: Optional[logging.Logger] = None
_initialization_error_occurred = False

try:
    _platformer_logger_instance = logging.getLogger("PlatformerLogger")

    if LOGGING_ENABLED:
        _platformer_logger_instance.setLevel(logging.DEBUG)

        for handler in list(_platformer_logger_instance.handlers): # Use list() for safe iteration while modifying
            _platformer_logger_instance.removeHandler(handler)
            handler.close()

        file_logging_successful = False
        if ENABLE_FILE_LOGGING:
            if os.path.exists(LOG_FILE_PATH):
                try:
                    os.remove(LOG_FILE_PATH)
                except OSError as e_remove:
                    sys.stderr.write(f"Logger Warning: Could not delete old log file {LOG_FILE_PATH}: {e_remove}\n")
            try:
                _file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
                _file_formatter = logging.Formatter(
                    "[%(asctime)s.%(msecs)03d] %(levelname)-7s %(filename)s:%(lineno)d (%(funcName)s): %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
                _file_handler.setFormatter(_file_formatter)
                _file_handler.setLevel(FILE_LOG_LEVEL)
                _platformer_logger_instance.addHandler(_file_handler)
                file_logging_successful = True
            except Exception as e_file_init:
                sys.stderr.write(f"Logger CRITICAL ERROR: Failed to initialize file logger at {LOG_FILE_PATH}: {e_file_init}\n")
                file_logging_successful = False
                _initialization_error_occurred = True


        if ENABLE_CONSOLE_LOGGING:
            _console_handler = logging.StreamHandler(sys.stdout)
            _console_formatter = logging.Formatter("CONSOLE %(levelname)-7s: %(message)s (%(filename)s:%(lineno)d)")
            _console_handler.setFormatter(_console_formatter)

            if file_logging_successful:
                _console_handler.setLevel(CONSOLE_LEVEL_WHEN_FILE_ACTIVE)
            else:
                if ENABLE_DEBUG_ON_CONSOLE_IF_FILE_FAILS:
                    _console_handler.setLevel(logging.DEBUG)
                else:
                    _console_handler.setLevel(CONSOLE_LEVEL_WHEN_FILE_FAILED)
            _platformer_logger_instance.addHandler(_console_handler)
        
        _platformer_logger_instance.propagate = False

        # Initial log messages (use _platformer_logger_instance directly here)
        if _platformer_logger_instance: # Check if it was created
            if file_logging_successful:
                _platformer_logger_instance.info(f"File logging initialized. Level: {logging.getLevelName(FILE_LOG_LEVEL)}. Output: {LOG_FILE_PATH}")
            if ENABLE_CONSOLE_LOGGING and _console_handler: # type: ignore
                _platformer_logger_instance.info(f"Console logging initialized. Level: {logging.getLevelName(_console_handler.level)}.")
            if not file_logging_successful and not ENABLE_CONSOLE_LOGGING:
                 _platformer_logger_instance.warning("Both file and console logging failed or are disabled. Logger will be silent.")

    else: # LOGGING_ENABLED is False
        if _platformer_logger_instance:
            for handler in list(_platformer_logger_instance.handlers):
                _platformer_logger_instance.removeHandler(handler)
                handler.close()
            _platformer_logger_instance.addHandler(logging.NullHandler())
            _platformer_logger_instance.setLevel(logging.CRITICAL + 1)
            _platformer_logger_instance.propagate = False
        # Basic print as logger is off.
        print("PlatformerLogger: Logging is globally DISABLED by configuration.")

except Exception as e_outer_init:
    # This is a critical failure in the logger setup itself.
    sys.stderr.write(f"PlatformerLogger FATAL INITIALIZATION ERROR: {e_outer_init}\n")
    import traceback
    traceback.print_exc(file=sys.stderr)
    _initialization_error_occurred = True
    # Define _platformer_logger_instance as a NullLogger if it failed completely
    if _platformer_logger_instance is None:
        _platformer_logger_instance = logging.getLogger("PlatformerLogger_Fallback")
        _platformer_logger_instance.addHandler(logging.NullHandler())
        _platformer_logger_instance.setLevel(logging.CRITICAL + 1)


# --- Define logging functions ---
# These are defined *after* the logger instance setup.

def _log_wrapper(level_func, message, *args, **kwargs):
    """Internal wrapper to ensure logger instance exists."""
    if LOGGING_ENABLED and _platformer_logger_instance:
        try:
            level_func(message, *args, **kwargs)
        except Exception as e_log_call:
            # Fallback to stderr if logging call itself fails
            sys.stderr.write(f"LOGGER CALL FAILED ({level_func.__name__}): {e_log_call}\nMessage was: {message}\n")
    elif not LOGGING_ENABLED:
        pass # Logging is globally off
    else: # _platformer_logger_instance is None or some other issue
        sys.stderr.write(f"Logger not available. Message ({level_func.__name__}): {message}\n")

def debug(message, *args, **kwargs):
    if _platformer_logger_instance: _log_wrapper(_platformer_logger_instance.debug, message, *args, **kwargs)
def info(message, *args, **kwargs):
    if _platformer_logger_instance: _log_wrapper(_platformer_logger_instance.info, message, *args, **kwargs)
def warning(message, *args, **kwargs):
    if _platformer_logger_instance: _log_wrapper(_platformer_logger_instance.warning, message, *args, **kwargs)
def error(message, *args, **kwargs):
    if _platformer_logger_instance: _log_wrapper(_platformer_logger_instance.error, message, *args, **kwargs)
def critical(message, *args, **kwargs):
    if _platformer_logger_instance: _log_wrapper(_platformer_logger_instance.critical, message, *args, **kwargs)

# Expose the logger instance itself for modules that might want to create child loggers
# or access it directly (though using the functions above is preferred).
logger = _platformer_logger_instance


def _format_float_for_log(value: Any, width: int, precision: int, default_na_width: Optional[int] = None) -> str:
    if default_na_width is None: default_na_width = width
    actual_value = value
    if callable(value):
        try: actual_value = value()
        except Exception: actual_value = float('nan')
    if isinstance(actual_value, (int, float)) and not math.isnan(actual_value):
        return f"{actual_value:{width}.{precision}f}"
    return f"{'N/A':>{default_na_width}}"


def log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    if not LOGGING_ENABLED or not ENABLE_DETAILED_PHYSICS_LOGS or not _platformer_logger_instance:
        return

    try:
        player_throttle_id = f"player_{str(getattr(player, 'player_id', 'unknown'))}"
        current_time_sec = time.time()
        last_log_time = _last_physics_log_time_by_player.get(player_throttle_id, 0.0)
        if current_time_sec - last_log_time < PHYSICS_LOG_INTERVAL_SEC: return
        _last_physics_log_time_by_player[player_throttle_id] = current_time_sec

        p_id_str = str(getattr(player, 'player_id', 'P?'))
        pos_x = getattr(player.pos, 'x', float('nan')); pos_y = getattr(player.pos, 'y', float('nan'))
        vel_x = getattr(player.vel, 'x', float('nan')); vel_y = getattr(player.vel, 'y', float('nan'))
        acc_x = getattr(player.acc, 'x', float('nan')); acc_y = getattr(player.acc, 'y', float('nan'))

        pos_x_s = _format_float_for_log(pos_x, 6, 2); pos_y_s = _format_float_for_log(pos_y, 6, 2)
        vel_x_s = _format_float_for_log(vel_x, 5, 2); vel_y_s = _format_float_for_log(vel_y, 5, 2)
        acc_x_s = _format_float_for_log(acc_x, 4, 2); acc_y_s = _format_float_for_log(acc_y, 4, 2)
        
        rect_s = str(getattr(player, 'rect', 'N/A')); on_g_s = str(getattr(player, 'on_ground', 'N/A'))
        state_s = str(getattr(player, 'state', 'N/A')); wall_t_s = str(getattr(player, 'touching_wall', 'N/A'))

        parts = [f"P{p_id_str} PHYS: {message_tag:<18} | Pos:({pos_x_s},{pos_y_s}) Vel:({vel_x_s},{vel_y_s}) "]
        if message_tag == "UPDATE_START": parts.append(f"Acc:({acc_x_s},{acc_y_s}) Rect:{rect_s} OnGround:{on_g_s} State:{state_s}")
        # (Simplified other branches for brevity, assuming they are similar to the provided previous version)
        elif "PLAT_COLL_CHECK" in message_tag and isinstance(extra_info, tuple) and len(extra_info) == 3: parts.append(f"PlayerR:{extra_info[0]} | PlatR:{extra_info[1]} | PlatT:{extra_info[2]}")
        elif "PLAT_COLL_DONE" in message_tag:
            axis_char = "x" if "X_" in message_tag else "y"
            parts.append(f"Pos.{axis_char}:{pos_x_s if axis_char=='x' else pos_y_s} | Vel.{axis_char}:{vel_x_s if axis_char=='x' else vel_y_s} {'WallT' if axis_char=='x' else 'OnG'}:{wall_t_s if axis_char=='x' else on_g_s}")
        elif isinstance(extra_info, str) and extra_info: parts.append(extra_info)
        
        _platformer_logger_instance.debug("".join(parts))
    except Exception as e:
        _platformer_logger_instance.error(f"Error in log_player_physics (P{getattr(player, 'player_id', '?')} tag '{message_tag}'): {e}", exc_info=False)


if _initialization_error_occurred:
    sys.stderr.write("PlatformerLogger: Logger setup encountered an error. Logging functionality may be impaired.\n")

if __name__ == "__main__":
    if LOGGING_ENABLED:
        info("Logger direct run: Info message.")
        debug("Logger direct run: Debug message.")
        warning("Logger direct run: Warning message.")
        error("Logger direct run: Error message.")
        critical("Logger direct run: Critical message.")

        class MockQPointF: # Minimal mock for testing log_player_physics
            def __init__(self, x_val=0.0, y_val=0.0): self._x = x_val; self._y = y_val
            def x(self): return self._x
            def y(self): return self._y
        class MockPlayer:
            def __init__(self, player_id): self.player_id = player_id; self.pos = MockQPointF(); self.vel = MockQPointF(); self.acc = MockQPointF()
        
        p1 = MockPlayer(1)
        ENABLE_DETAILED_PHYSICS_LOGS = True
        log_player_physics(p1, "TEST_PHYS_LOG", "Some extra data.")
        log_player_physics(p1, "UPDATE_START")

        print(f"Test logs (if file logging enabled) written to {LOG_FILE_PATH if 'LOG_FILE_PATH' in globals() else 'UNKNOWN'}")
    else:
        print("Logging is globally disabled. No log output from this direct run.")

#################### END OF FILE: logger.py ####################