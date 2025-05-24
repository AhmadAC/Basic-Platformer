# logger.py
# version 1.0.0.6 (Log on change + rate limiting for log_player_physics)

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
FILE_LOG_LEVEL = logging.DEBUG # Keep DEBUG to allow "log on change" messages
ENABLE_CONSOLE_LOGGING = True
CONSOLE_LEVEL_WHEN_FILE_ACTIVE = logging.INFO # Console less verbose if file is working
CONSOLE_LEVEL_WHEN_FILE_FAILED = logging.DEBUG # Console more verbose if file fails
ENABLE_DEBUG_ON_CONSOLE_IF_FILE_FAILS = True # Overrides CONSOLE_LEVEL_WHEN_FILE_FAILED if True

ENABLE_DETAILED_PHYSICS_LOGS = True # Master switch for log_player_physics
PHYSICS_LOG_INTERVAL_SEC = 1.0 # Rate limit: max 1 log per second *per specific change type*
# --- ---

LOG_FILENAME = "platformer_debug.log"
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILENAME)

_platformer_logger_instance: Optional[logging.Logger] = None
_initialization_error_occurred = False

# --- Rate Limiter Utility (can be in utils.py, included here for self-containment) ---
class RateLimiter:
    def __init__(self, default_period_sec: float = 1.0):
        self.timestamps: Dict[str, float] = collections.defaultdict(float)
        self.default_period_sec = default_period_sec

    def can_proceed(self, key: str, period_sec: Optional[float] = None) -> bool:
        effective_period = period_sec if period_sec is not None else self.default_period_sec
        current_time = time.monotonic() # Use monotonic time for intervals
        last_time = self.timestamps[key]

        if current_time - last_time >= effective_period:
            self.timestamps[key] = current_time # Update timestamp *only when proceeding*
            return True
        return False

# --- Global instances for physics logging ---
_physics_log_rate_limiter = RateLimiter(default_period_sec=PHYSICS_LOG_INTERVAL_SEC)
_last_physics_significant_data: Dict[Tuple[str, str], Tuple[Any, ...]] = {}


try:
    _platformer_logger_instance = logging.getLogger("PlatformerLogger")

    if LOGGING_ENABLED:
        _platformer_logger_instance.setLevel(logging.DEBUG) # Root logger for this instance

        # Clear existing handlers for this specific logger instance to prevent duplicates on re-init
        for handler in list(_platformer_logger_instance.handlers):
            _platformer_logger_instance.removeHandler(handler)
            handler.close()

        file_logging_successful = False
        if ENABLE_FILE_LOGGING:
            if os.path.exists(LOG_FILE_PATH):
                try:
                    # Try to open in append mode first to see if it's locked, then try remove
                    # This is a bit complex; simpler to just try to remove.
                    # os.remove(LOG_FILE_PATH)
                    # For safety, let's just append if it exists, or clear if mode='w' handles it.
                    # The FileHandler with mode='w' will overwrite.
                    pass
                except OSError as e_remove:
                    sys.stderr.write(f"Logger Warning: Could not prepare old log file {LOG_FILE_PATH}: {e_remove}\n")
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
                _initialization_error_occurred = True

        if ENABLE_CONSOLE_LOGGING:
            _console_handler = logging.StreamHandler(sys.stdout) # Use stdout for general console logs
            _console_formatter = logging.Formatter("CONSOLE %(levelname)-7s: %(message)s (%(filename)s:%(lineno)d)")
            _console_handler.setFormatter(_console_formatter)

            if file_logging_successful:
                _console_handler.setLevel(CONSOLE_LEVEL_WHEN_FILE_ACTIVE)
            else: # File logging failed or is disabled
                _console_handler.setLevel(logging.DEBUG if ENABLE_DEBUG_ON_CONSOLE_IF_FILE_FAILS else CONSOLE_LEVEL_WHEN_FILE_FAILED)
            _platformer_logger_instance.addHandler(_console_handler)
        
        _platformer_logger_instance.propagate = False # Prevent messages from going to root logger if it has handlers

        if _platformer_logger_instance:
            if file_logging_successful:
                _platformer_logger_instance.info(f"File logging initialized. Level: {logging.getLevelName(FILE_LOG_LEVEL)}. Output: {LOG_FILE_PATH}")
            if ENABLE_CONSOLE_LOGGING and vars().get('_console_handler'): # Check if _console_handler was defined
                _platformer_logger_instance.info(f"Console logging initialized. Level: {logging.getLevelName(vars()['_console_handler'].level)}.")
            if not file_logging_successful and not ENABLE_CONSOLE_LOGGING:
                 _platformer_logger_instance.warning("Both file and console logging failed or are disabled. Logger will be silent.")
    else:
        if _platformer_logger_instance:
            for handler in list(_platformer_logger_instance.handlers):
                _platformer_logger_instance.removeHandler(handler)
                handler.close()
            _platformer_logger_instance.addHandler(logging.NullHandler())
            _platformer_logger_instance.setLevel(logging.CRITICAL + 1) # Effectively disable
            _platformer_logger_instance.propagate = False
        sys.stdout.write("PlatformerLogger: Logging is globally DISABLED by configuration.\n")

except Exception as e_outer_init:
    sys.stderr.write(f"PlatformerLogger FATAL INITIALIZATION ERROR: {e_outer_init}\n")
    import traceback
    traceback.print_exc(file=sys.stderr)
    _initialization_error_occurred = True
    if _platformer_logger_instance is None: # Ensure it's at least a NullLogger
        _platformer_logger_instance = logging.getLogger("PlatformerLogger_Critical_Fallback")
        _platformer_logger_instance.addHandler(logging.NullHandler())
        _platformer_logger_instance.setLevel(logging.CRITICAL + 1)

# --- Define logging functions robustly ---
def _log_wrapper(level_func_name: str, message: str, *args, **kwargs):
    if LOGGING_ENABLED and _platformer_logger_instance:
        try:
            log_method: Optional[Callable] = getattr(_platformer_logger_instance, level_func_name, None)
            if log_method:
                log_method(message, *args, **kwargs)
            else: # Should not happen if logger instance is valid
                sys.stderr.write(f"Logger method '{level_func_name}' not found. Message: {message}\n")
        except Exception as e_log_call:
            sys.stderr.write(f"LOGGER CALL FAILED ({level_func_name}): {e_log_call}\nMessage was: {message}\n")
    elif not LOGGING_ENABLED:
        pass
    else:
        sys.stderr.write(f"Logger not available. Message ({level_func_name}): {message}\n")

def debug(message, *args, **kwargs): _log_wrapper("debug", message, *args, **kwargs)
def info(message, *args, **kwargs): _log_wrapper("info", message, *args, **kwargs)
def warning(message, *args, **kwargs): _log_wrapper("warning", message, *args, **kwargs)
def error(message, *args, **kwargs): _log_wrapper("error", message, *args, **kwargs)
def critical(message, *args, **kwargs): _log_wrapper("critical", message, *args, **kwargs)

logger = _platformer_logger_instance # Expose the instance

def _format_float_for_log(value: Any, width: int, precision: int, default_na_width: Optional[int] = None) -> str:
    # (Same as your provided version)
    if default_na_width is None: default_na_width = width
    actual_value = value
    if callable(value):
        try: actual_value = value()
        except Exception: actual_value = float('nan')
    if isinstance(actual_value, (int, float)) and not math.isnan(actual_value):
        return f"{actual_value:{width}.{precision}f}"
    return f"{'N/A':>{default_na_width}}"


def log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    """
    Logs player physics details if enabled, data has changed significantly, and rate limit allows.
    """
    if not LOGGING_ENABLED or not ENABLE_DETAILED_PHYSICS_LOGS or not _platformer_logger_instance:
        return

    try:
        player_id_str = str(getattr(player, 'player_id', 'unknownP'))
        
        # --- Define what constitutes "significant data" for this log event ---
        # This might need to be adjusted based on the `message_tag`.
        # For a general physics update, we can capture core kinematic values.
        # Using tuples makes them hashable for dictionary keys.
        
        # Extract primary values, handling potential missing attributes gracefully
        pos_x_val = getattr(player.pos, 'x', float('nan'))() if hasattr(player, 'pos') and hasattr(player.pos, 'x') else float('nan')
        pos_y_val = getattr(player.pos, 'y', float('nan'))() if hasattr(player, 'pos') and hasattr(player.pos, 'y') else float('nan')
        vel_x_val = getattr(player.vel, 'x', float('nan'))() if hasattr(player, 'vel') and hasattr(player.vel, 'x') else float('nan')
        vel_y_val = getattr(player.vel, 'y', float('nan'))() if hasattr(player, 'vel') and hasattr(player.vel, 'y') else float('nan')
        acc_x_val = getattr(player.acc, 'x', float('nan'))() if hasattr(player, 'acc') and hasattr(player.acc, 'x') else float('nan')
        acc_y_val = getattr(player.acc, 'y', float('nan'))() if hasattr(player, 'acc') and hasattr(player.acc, 'y') else float('nan')
        
        # Round to 1 decimal place for change detection to reduce noise from tiny float variations
        current_significant_data = (
            round(pos_x_val, 1), round(pos_y_val, 1),
            round(vel_x_val, 1), round(vel_y_val, 1),
            round(acc_x_val, 1), round(acc_y_val, 1),
            getattr(player, 'state', 'N/A'),
            getattr(player, 'on_ground', False),
            getattr(player, 'touching_wall', 0)
            # Add other key attributes for specific message_tags if needed
        )

        log_key_for_data_change = (player_id_str, message_tag) # Tuple for dict key
        last_data = _last_physics_significant_data.get(log_key_for_data_change)
        data_has_changed = (last_data != current_significant_data)

        if data_has_changed:
            rate_limit_key = f"physics_{player_id_str}_{message_tag}"
            if _physics_log_rate_limiter.can_proceed(rate_limit_key, period_sec=PHYSICS_LOG_INTERVAL_SEC):
                # Construct the full log message using precise values
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
                
                _platformer_logger_instance.debug(log_message)
                _last_physics_significant_data[log_key_for_data_change] = current_significant_data
            # else: Data changed, but rate-limited this time.
        # else: Data has not significantly changed, do not log.

    except Exception as e: # Catch errors within the logging function itself
        if _platformer_logger_instance:
            _platformer_logger_instance.error(
                f"Error in log_player_physics itself (P{getattr(player, 'player_id', '?')} tag '{message_tag}'): {e}",
                exc_info=False # Keep exc_info False to avoid flooding logs *from* the logger
            )
        else:
            sys.stderr.write(f"Error in log_player_physics (P{getattr(player, 'player_id', '?')} tag '{message_tag}'): {e}\n")

# --- Final check and message if logger initialization failed ---
if _initialization_error_occurred:
    sys.stderr.write("PlatformerLogger: Logger setup encountered an error during initialization. Logging functionality may be impaired or using fallbacks.\n")

if __name__ == "__main__":
    if LOGGING_ENABLED and _platformer_logger_instance:
        info("Logger direct run: Info message.")
        debug("Logger direct run: Debug message.")
        warning("Logger direct run: Warning message.")
        error("Logger direct run: Error message.")
        critical("Logger direct run: Critical message.")

        class MockQPointF:
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
        
        print("\n--- Testing log_player_physics (expect up to 1 log per tag per second if data changes) ---")
        if ENABLE_DETAILED_PHYSICS_LOGS:
            print(f"PHYSICS_LOG_INTERVAL_SEC = {PHYSICS_LOG_INTERVAL_SEC}")
            log_player_physics(p1, "TEST_TAG_1", "Initial state.") # Should log
            time.sleep(0.1)
            log_player_physics(p1, "TEST_TAG_1", "No change yet.") # Should not log (data same)
            time.sleep(0.1)
            p1.pos = MockQPointF(10.5, 20.5) # Change data
            log_player_physics(p1, "TEST_TAG_1", "Pos changed slightly.") # Should log (data changed, period might not be over for rate limit)
            
            time.sleep(PHYSICS_LOG_INTERVAL_SEC) # Wait for rate limit period
            
            p1.vel = MockQPointF(2.0, 1.0) # Change data again
            log_player_physics(p1, "TEST_TAG_1", "Vel changed significantly.") # Should log (data changed, period over)
            
            log_player_physics(p1, "TEST_TAG_2", "Different tag, first log.") # Should log (new tag)
            p1.state = "run"
            log_player_physics(p1, "TEST_TAG_2", "Different tag, state changed.") # Should log (data changed for this tag)
        else:
            print("ENABLE_DETAILED_PHYSICS_LOGS is False. log_player_physics will not produce output.")

        print(f"\nTest logs (if file logging enabled) likely written to: {LOG_FILE_PATH}")
        print("Check console output based on your CONSOLE_LEVEL settings.")
    else:
        print("Logging is globally disabled or logger instance failed to initialize. No log output from this direct run.")