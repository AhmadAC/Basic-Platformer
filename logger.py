# logger.py
# version 1.0.0.7 (Shared global rate limit for all DEBUG logs, including log_player_physics output)

from typing import List, Dict, Tuple, Any, Optional, Callable
import logging
import os
import sys
import time
import math
import collections # For defaultdict

# --- USER CONFIGURABLE LOGGING SETTINGS ---
LOGGING_ENABLED = True
ENABLE_FILE_LOGGING = True
FILE_LOG_LEVEL = logging.DEBUG 
ENABLE_CONSOLE_LOGGING = True
CONSOLE_LEVEL_WHEN_FILE_ACTIVE = logging.INFO 
CONSOLE_LEVEL_WHEN_FILE_FAILED = logging.DEBUG 
ENABLE_DEBUG_ON_CONSOLE_IF_FILE_FAILS = True 

ENABLE_DETAILED_PHYSICS_LOGS = True 
# MODIFIED: Global interval for debug logs and physics logs
# This interval is shared between log_player_physics and generic logger.debug() calls.
DEBUG_LOG_INTERVAL_SEC = 1.0 
# --- ---

LOG_FILENAME = "platformer_debug.log"
# Path modification for robustness if this script is moved
_current_script_path = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.join(_current_script_path, LOG_FILENAME)


_platformer_logger_instance: Optional[logging.Logger] = None
_initialization_error_occurred = False

class RateLimiter:
    def __init__(self, default_period_sec: float = 1.0):
        self.timestamps: Dict[str, float] = collections.defaultdict(float)
        self.default_period_sec = default_period_sec

    def can_proceed(self, key: str, period_sec: Optional[float] = None) -> bool:
        effective_period = period_sec if period_sec is not None else self.default_period_sec
        current_time = time.monotonic() 
        last_time = self.timestamps[key] 

        if current_time - last_time >= effective_period:
            self.timestamps[key] = current_time 
            return True
        return False

# Single rate limiter for all DEBUG logs, including those from log_player_physics
_shared_debug_rate_limiter = RateLimiter(default_period_sec=DEBUG_LOG_INTERVAL_SEC)
_SHARED_DEBUG_LOG_KEY = "global_debug_log_tick" # Common key for the shared limiter

_last_physics_significant_data: Dict[Tuple[str, str], Tuple[Any, ...]] = {}


try:
    _platformer_logger_instance = logging.getLogger("PlatformerLogger")

    if LOGGING_ENABLED:
        _platformer_logger_instance.setLevel(logging.DEBUG) # Process all debug messages internally

        # Clear existing handlers to prevent duplication if re-initialized
        for handler in list(_platformer_logger_instance.handlers):
            _platformer_logger_instance.removeHandler(handler)
            handler.close()

        file_logging_successful = False
        if ENABLE_FILE_LOGGING:
            if os.path.exists(LOG_FILE_PATH):
                try:
                    # 'w' mode in FileHandler will overwrite, so no explicit removal needed here
                    pass 
                except OSError as e_remove:
                    sys.stderr.write(f"Logger Warning: Could not prepare old log file {LOG_FILE_PATH}: {e_remove}\n")
            try:
                _file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
                _file_formatter = logging.Formatter(
                    "[%(asctime)s.%(msecs)03d] %(levelname)-7s %(filename)s:%(lineno)d (%(funcName)s): %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
                _file_handler.setFormatter(_file_formatter)
                _file_handler.setLevel(FILE_LOG_LEVEL) # File handler logs at specified level
                _platformer_logger_instance.addHandler(_file_handler)
                file_logging_successful = True
            except Exception as e_file_init:
                sys.stderr.write(f"Logger CRITICAL ERROR: Failed to initialize file logger at {LOG_FILE_PATH}: {e_file_init}\n")
                _initialization_error_occurred = True

        if ENABLE_CONSOLE_LOGGING:
            _console_handler = logging.StreamHandler(sys.stdout) 
            _console_formatter = logging.Formatter("CONSOLE %(levelname)-7s: %(message)s (%(filename)s:%(lineno)d)")
            _console_handler.setFormatter(_console_formatter)

            if file_logging_successful:
                _console_handler.setLevel(CONSOLE_LEVEL_WHEN_FILE_ACTIVE)
            else: 
                _console_handler.setLevel(logging.DEBUG if ENABLE_DEBUG_ON_CONSOLE_IF_FILE_FAILS else CONSOLE_LEVEL_WHEN_FILE_FAILED)
            _platformer_logger_instance.addHandler(_console_handler)
        
        _platformer_logger_instance.propagate = False # Prevent logs from going to root logger

        # Initial log messages after setup
        if _platformer_logger_instance: # Check if instance is valid
            if file_logging_successful:
                _platformer_logger_instance.info(f"File logging initialized. Level: {logging.getLevelName(FILE_LOG_LEVEL)}. Output: {LOG_FILE_PATH}")
            if ENABLE_CONSOLE_LOGGING and vars().get('_console_handler'): # Check if console handler was actually added
                _platformer_logger_instance.info(f"Console logging initialized. Level: {logging.getLevelName(vars()['_console_handler'].level)}.")
            if not file_logging_successful and not ENABLE_CONSOLE_LOGGING:
                 _platformer_logger_instance.warning("Both file and console logging failed or are disabled. Logger will be silent.")
    else: # LOGGING_ENABLED is False
        if _platformer_logger_instance: # Ensure instance exists to silence it
            for handler in list(_platformer_logger_instance.handlers): # Remove any handlers
                _platformer_logger_instance.removeHandler(handler)
                handler.close()
            _platformer_logger_instance.addHandler(logging.NullHandler()) # Add NullHandler to discard all logs
            _platformer_logger_instance.setLevel(logging.CRITICAL + 1) # Set level higher than any standard level
            _platformer_logger_instance.propagate = False
        sys.stdout.write("PlatformerLogger: Logging is globally DISABLED by configuration.\n")

except Exception as e_outer_init:
    sys.stderr.write(f"PlatformerLogger FATAL INITIALIZATION ERROR: {e_outer_init}\n")
    import traceback
    traceback.print_exc(file=sys.stderr)
    _initialization_error_occurred = True
    if _platformer_logger_instance is None: # Fallback if logger creation failed
        _platformer_logger_instance = logging.getLogger("PlatformerLogger_Critical_Fallback")
        _platformer_logger_instance.addHandler(logging.NullHandler()) 
        _platformer_logger_instance.setLevel(logging.CRITICAL + 1)

def _log_wrapper(level_func_name: str, message: str, *args, **kwargs):
    if LOGGING_ENABLED and _platformer_logger_instance:
        # --- MODIFICATION START for global DEBUG rate limit ---
        if level_func_name == "debug":
            # All calls to logger.debug() from external modules will pass through here.
            # They will share the rate limit with log_player_physics output.
            if not _shared_debug_rate_limiter.can_proceed(_SHARED_DEBUG_LOG_KEY, period_sec=DEBUG_LOG_INTERVAL_SEC):
                return # Skip logging this debug message due to rate limit
        # --- MODIFICATION END ---
        try:
            log_method: Optional[Callable] = getattr(_platformer_logger_instance, level_func_name, None)
            if log_method:
                log_method(message, *args, **kwargs)
            else: 
                # This case should ideally not happen if level_func_name is always valid
                sys.stderr.write(f"Logger method '{level_func_name}' not found. Message: {message}\n")
        except Exception as e_log_call:
            # Log errors during the logging call itself to stderr to avoid recursion
            sys.stderr.write(f"LOGGER CALL FAILED ({level_func_name}): {e_log_call}\nMessage was: {message}\n")
    elif not LOGGING_ENABLED:
        pass # Logging disabled, do nothing
    else: # _platformer_logger_instance is None, indicating a severe setup issue
        sys.stderr.write(f"Logger not available. Message ({level_func_name}): {message}\n")

# Public logging functions that use the wrapper
def debug(message, *args, **kwargs): _log_wrapper("debug", message, *args, **kwargs)
def info(message, *args, **kwargs): _log_wrapper("info", message, *args, **kwargs)
def warning(message, *args, **kwargs): _log_wrapper("warning", message, *args, **kwargs)
def error(message, *args, **kwargs): _log_wrapper("error", message, *args, **kwargs)
def critical(message, *args, **kwargs): _log_wrapper("critical", message, *args, **kwargs)

# Expose the logger instance directly if needed by advanced users, though helper functions are preferred.
logger = _platformer_logger_instance 

def _format_float_for_log(value: Any, width: int, precision: int, default_na_width: Optional[int] = None) -> str:
    if default_na_width is None: default_na_width = width
    actual_value = value
    if callable(value): # Handle cases where value might be a method (e.g., QPointF.x())
        try: actual_value = value()
        except Exception: actual_value = float('nan') # Or some other placeholder if call fails
    
    if isinstance(actual_value, (int, float)) and not math.isnan(actual_value):
        return f"{actual_value:{width}.{precision}f}"
    return f"{'N/A':>{default_na_width}}"


def log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    if not LOGGING_ENABLED or not ENABLE_DETAILED_PHYSICS_LOGS or not _platformer_logger_instance:
        return

    try:
        player_id_str = str(getattr(player, 'player_id', 'unknownP'))
        
        # Safely get physics values, defaulting to NaN if attributes are missing
        pos_x_val = getattr(player.pos, 'x', float('nan'))() if hasattr(player, 'pos') and hasattr(player.pos, 'x') and callable(getattr(player.pos, 'x')) else getattr(player.pos, 'x', float('nan')) if hasattr(player, 'pos') else float('nan')
        pos_y_val = getattr(player.pos, 'y', float('nan'))() if hasattr(player, 'pos') and hasattr(player.pos, 'y') and callable(getattr(player.pos, 'y')) else getattr(player.pos, 'y', float('nan')) if hasattr(player, 'pos') else float('nan')
        vel_x_val = getattr(player.vel, 'x', float('nan'))() if hasattr(player, 'vel') and hasattr(player.vel, 'x') and callable(getattr(player.vel, 'x')) else getattr(player.vel, 'x', float('nan')) if hasattr(player, 'vel') else float('nan')
        vel_y_val = getattr(player.vel, 'y', float('nan'))() if hasattr(player, 'vel') and hasattr(player.vel, 'y') and callable(getattr(player.vel, 'y')) else getattr(player.vel, 'y', float('nan')) if hasattr(player, 'vel') else float('nan')
        acc_x_val = getattr(player.acc, 'x', float('nan'))() if hasattr(player, 'acc') and hasattr(player.acc, 'x') and callable(getattr(player.acc, 'x')) else getattr(player.acc, 'x', float('nan')) if hasattr(player, 'acc') else float('nan')
        acc_y_val = getattr(player.acc, 'y', float('nan'))() if hasattr(player, 'acc') and hasattr(player.acc, 'y') and callable(getattr(player.acc, 'y')) else getattr(player.acc, 'y', float('nan')) if hasattr(player, 'acc') else float('nan')

        current_significant_data = (
            round(pos_x_val, 1) if not math.isnan(pos_x_val) else 'NaN',
            round(pos_y_val, 1) if not math.isnan(pos_y_val) else 'NaN',
            round(vel_x_val, 1) if not math.isnan(vel_x_val) else 'NaN',
            round(vel_y_val, 1) if not math.isnan(vel_y_val) else 'NaN',
            round(acc_x_val, 1) if not math.isnan(acc_x_val) else 'NaN',
            round(acc_y_val, 1) if not math.isnan(acc_y_val) else 'NaN',
            getattr(player, 'state', 'N/A'),
            getattr(player, 'on_ground', False),
            getattr(player, 'touching_wall', 0)
        )

        log_key_for_data_change = (player_id_str, message_tag) 
        last_data = _last_physics_significant_data.get(log_key_for_data_change)
        data_has_changed = (last_data != current_significant_data)

        if data_has_changed:
            # Use the shared rate limiter and key
            if _shared_debug_rate_limiter.can_proceed(_SHARED_DEBUG_LOG_KEY, period_sec=DEBUG_LOG_INTERVAL_SEC):
                pos_x_s = _format_float_for_log(pos_x_val, 6, 2)
                pos_y_s = _format_float_for_log(pos_y_val, 6, 2)
                vel_x_s = _format_float_for_log(vel_x_val, 5, 2)
                vel_y_s = _format_float_for_log(vel_y_val, 5, 2)
                acc_x_s = _format_float_for_log(acc_x_val, 4, 2)
                acc_y_s = _format_float_for_log(acc_y_val, 4, 2)
                state_s = str(getattr(player, 'state', 'N/A'))
                on_g_s = str(getattr(player, 'on_ground', 'N/A'))
                wall_t_s = str(getattr(player, 'touching_wall', 'N/A'))

                log_message = (f"P{player_id_str} PHYS-CHG: {message_tag:<18} | "
                               f"Pos:({pos_x_s},{pos_y_s}) Vel:({vel_x_s},{vel_y_s}) Acc:({acc_x_s},{acc_y_s}) "
                               f"State:{state_s} OnG:{on_g_s} WallT:{wall_t_s}")
                if isinstance(extra_info, str) and extra_info:
                    log_message += f" | Extra: {extra_info}"
                elif isinstance(extra_info, (tuple, list)) and extra_info:
                    extra_info_str = ", ".join([str(item) for item in extra_info])
                    log_message += f" | Extra: ({extra_info_str})"
                
                # IMPORTANT: log_player_physics calls the underlying logger directly (_platformer_logger_instance),
                # so it won't be double-filtered by _log_wrapper's rate limit check.
                # The check here using _shared_debug_rate_limiter is sufficient for its output.
                _platformer_logger_instance.debug(log_message)
                _last_physics_significant_data[log_key_for_data_change] = current_significant_data
    except Exception as e: 
        # Prevent logging errors from crashing the application
        if _platformer_logger_instance: # Check if logger is available
            _platformer_logger_instance.error(
                f"Error in log_player_physics itself (P{getattr(player, 'player_id', '?')} tag '{message_tag}'): {e}",
                exc_info=False # Set to True for full traceback if needed for debugging logger itself
            )
        else: # Fallback if logger itself is broken
            sys.stderr.write(f"Error in log_player_physics (P{getattr(player, 'player_id', '?')} tag '{message_tag}'): {e}\n")

if _initialization_error_occurred:
    sys.stderr.write("PlatformerLogger: Logger setup encountered an error during initialization. Logging functionality may be impaired or using fallbacks.\n")

if __name__ == "__main__":
    # Update main for testing the new shared limiter
    if LOGGING_ENABLED and _platformer_logger_instance:
        info("Logger direct run: Info message 1.") # Not rate-limited by new DEBUG logic
        debug("Logger direct run: Debug message 1 (should log).") # Should log, consumes slot
        debug("Logger direct run: Debug message 2 (should be rate-limited).") 
        info("Logger direct run: Info message 2 (should log, not debug).")
        
        time.sleep(DEBUG_LOG_INTERVAL_SEC / 2)
        debug("Logger direct run: Debug message 3 (before interval, should be rate-limited).") 

        print(f"Waiting for {DEBUG_LOG_INTERVAL_SEC}s...")
        time.sleep(DEBUG_LOG_INTERVAL_SEC) # Ensure interval passed since last successful debug log
        
        debug("Logger direct run: Debug message 4 (after interval, should log).") # Should log, consumes slot

        class MockQPointF: # Simplified Mock for testing
            def __init__(self, x_val=0.0, y_val=0.0): self._x = x_val; self._y = y_val
            def x(self): return self._x
            def y(self): return self._y
        class MockPlayer:
            def __init__(self, player_id):
                self.player_id = player_id
                self.pos = MockQPointF(10.0, 20.0)
                self.vel = MockQPointF(1.0, 0.5)
                self.acc = MockQPointF(0.0, 0.7)
                self.state = "idle"
                self.on_ground = True
                self.touching_wall = 0
        
        p1 = MockPlayer(1)
        p2 = MockPlayer(2)
        
        print(f"\n--- Testing log_player_physics with shared rate limit (expect 1 DEBUG log per {DEBUG_LOG_INTERVAL_SEC}s total) ---")
        if ENABLE_DETAILED_PHYSICS_LOGS:
            print(f"DEBUG_LOG_INTERVAL_SEC = {DEBUG_LOG_INTERVAL_SEC}")
            
            time.sleep(DEBUG_LOG_INTERVAL_SEC) # Ensure fresh slot
            debug("Generic debug before physics log (Msg 5, should log).") # Consumes slot
            log_player_physics(p1, "PHYS_TEST_1", "Initial state P1 (should be rate-limited).") 
            
            time.sleep(DEBUG_LOG_INTERVAL_SEC) # Ensure fresh slot
            log_player_physics(p1, "PHYS_TEST_2", "State P1 after wait (Msg 6, should log).") # Should log, consumes slot
            
            p1.pos = MockQPointF(10.5, 20.5) # Change data for p1
            debug("Generic debug after physics log (should be rate-limited).") 
            log_player_physics(p1, "PHYS_TEST_3", "Pos changed P1 (should be rate-limited, data changed but slot taken).")

            time.sleep(DEBUG_LOG_INTERVAL_SEC) # Ensure fresh slot
            log_player_physics(p1, "PHYS_TEST_4", "Pos changed P1 again (Msg 7, should log, data changed & slot free).") 
            
            p2.pos = MockQPointF(50,50) # Change data for p2
            log_player_physics(p2, "PHYS_TEST_P2_1", "Initial state P2 (should be rate-limited).") 

        else:
            print("ENABLE_DETAILED_PHYSICS_LOGS is False. log_player_physics will not produce output (other than errors).")

        print(f"\nTest logs (if file logging enabled) likely written to: {LOG_FILE_PATH}")
        print("Check console output based on your CONSOLE_LEVEL settings.")
    else:
        print("Logging is globally disabled or logger instance failed to initialize. No log output from this direct run.")