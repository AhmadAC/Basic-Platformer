# main_game/logger.py
# version 1.0.0.8 (Confirmed self-containment and shared DEBUG rate limiter functionality)

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
DEBUG_LOG_INTERVAL_SEC = 1.0 # Shared interval for all DEBUG logs
# --- ---

LOG_FILENAME = "platformer_debug.log"
_current_script_path = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.join(_current_script_path, LOG_FILENAME)


_platformer_logger_instance: Optional[logging.Logger] = None
_initialization_error_occurred = False # Tracks if logger setup had critical issues

class RateLimiter:
    """A simple rate limiter to control log frequency for specific keys."""
    def __init__(self, default_period_sec: float = 1.0):
        self.timestamps: Dict[str, float] = collections.defaultdict(float)
        self.default_period_sec = default_period_sec

    def can_proceed(self, key: str, period_sec: Optional[float] = None) -> bool:
        effective_period = period_sec if period_sec is not None else self.default_period_sec
        current_time = time.monotonic()
        last_time = self.timestamps[key] # defaultdict provides 0.0 if key not present

        if current_time - last_time >= effective_period:
            self.timestamps[key] = current_time
            return True
        return False

_shared_debug_rate_limiter = RateLimiter(default_period_sec=DEBUG_LOG_INTERVAL_SEC)
_SHARED_DEBUG_LOG_KEY = "global_debug_log_tick"

_last_physics_significant_data: Dict[Tuple[str, str], Tuple[Any, ...]] = {}

# Initialize logger instance
try:
    _platformer_logger_instance = logging.getLogger("PlatformerLogger")

    if LOGGING_ENABLED:
        _platformer_logger_instance.setLevel(logging.DEBUG) # Process all debug messages internally

        for handler in list(_platformer_logger_instance.handlers): # Clear existing handlers
            _platformer_logger_instance.removeHandler(handler)
            handler.close()

        _file_handler_instance: Optional[logging.FileHandler] = None
        _console_handler_instance: Optional[logging.StreamHandler] = None
        file_logging_successful = False

        if ENABLE_FILE_LOGGING:
            try:
                _file_handler_instance = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
                _file_formatter = logging.Formatter(
                    "[%(asctime)s.%(msecs)03d] %(levelname)-7s %(filename)s:%(lineno)d (%(funcName)s): %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
                _file_handler_instance.setFormatter(_file_formatter)
                _file_handler_instance.setLevel(FILE_LOG_LEVEL)
                _platformer_logger_instance.addHandler(_file_handler_instance)
                file_logging_successful = True
            except Exception as e_file_init:
                sys.stderr.write(f"Logger CRITICAL ERROR: Failed to initialize file logger at {LOG_FILE_PATH}: {e_file_init}\n")
                _initialization_error_occurred = True

        if ENABLE_CONSOLE_LOGGING:
            _console_handler_instance = logging.StreamHandler(sys.stdout)
            _console_formatter = logging.Formatter("CONSOLE %(levelname)-7s: %(message)s (%(filename)s:%(lineno)d)")
            _console_handler_instance.setFormatter(_console_formatter)

            if file_logging_successful:
                _console_handler_instance.setLevel(CONSOLE_LEVEL_WHEN_FILE_ACTIVE)
            else:
                _console_handler_instance.setLevel(logging.DEBUG if ENABLE_DEBUG_ON_CONSOLE_IF_FILE_FAILS else CONSOLE_LEVEL_WHEN_FILE_FAILED)
            _platformer_logger_instance.addHandler(_console_handler_instance)

        _platformer_logger_instance.propagate = False

        if file_logging_successful:
            _platformer_logger_instance.info(f"File logging initialized. Level: {logging.getLevelName(FILE_LOG_LEVEL)}. Output: {LOG_FILE_PATH}")
        if ENABLE_CONSOLE_LOGGING and _console_handler_instance:
            _platformer_logger_instance.info(f"Console logging initialized. Level: {logging.getLevelName(_console_handler_instance.level)}.")
        if not file_logging_successful and not (ENABLE_CONSOLE_LOGGING and _console_handler_instance):
            _platformer_logger_instance.warning("Both file and console logging failed or are disabled. Logger will be silent.")
    else:
        if _platformer_logger_instance:
            for handler in list(_platformer_logger_instance.handlers):
                _platformer_logger_instance.removeHandler(handler)
                handler.close()
            _platformer_logger_instance.addHandler(logging.NullHandler())
            _platformer_logger_instance.setLevel(logging.CRITICAL + 1)
            _platformer_logger_instance.propagate = False
        sys.stdout.write("PlatformerLogger: Logging is globally DISABLED by configuration.\n")

except Exception as e_outer_init:
    sys.stderr.write(f"PlatformerLogger FATAL INITIALIZATION ERROR: {e_outer_init}\n")
    import traceback
    traceback.print_exc(file=sys.stderr)
    _initialization_error_occurred = True
    if _platformer_logger_instance is None:
        _platformer_logger_instance = logging.getLogger("PlatformerLogger_Critical_Fallback")
        _platformer_logger_instance.addHandler(logging.NullHandler())
        _platformer_logger_instance.setLevel(logging.CRITICAL + 1)


def _log_wrapper(level_func_name: str, message: str, *args: Any, **kwargs: Any):
    if not LOGGING_ENABLED:
        return
    if not _platformer_logger_instance:
        sys.stderr.write(f"Logger not available due to init error. Message ({level_func_name}): {message}\n")
        return

    if level_func_name == "debug":
        if not _shared_debug_rate_limiter.can_proceed(_SHARED_DEBUG_LOG_KEY, period_sec=DEBUG_LOG_INTERVAL_SEC):
            return
    try:
        log_method: Optional[Callable[..., None]] = getattr(_platformer_logger_instance, level_func_name, None)
        if log_method:
            log_method(message, *args, **kwargs)
        else:
            sys.stderr.write(f"Logger method '{level_func_name}' not found. Message: {message}\n")
    except Exception as e_log_call:
        sys.stderr.write(f"LOGGER CALL FAILED ({level_func_name}): {e_log_call}\nMessage was: {message}\n")

def debug(message: str, *args: Any, **kwargs: Any): _log_wrapper("debug", message, *args, **kwargs)
def info(message: str, *args: Any, **kwargs: Any): _log_wrapper("info", message, *args, **kwargs)
def warning(message: str, *args: Any, **kwargs: Any): _log_wrapper("warning", message, *args, **kwargs)
def error(message: str, *args: Any, **kwargs: Any): _log_wrapper("error", message, *args, **kwargs)
def critical(message: str, *args: Any, **kwargs: Any): _log_wrapper("critical", message, *args, **kwargs)

logger = _platformer_logger_instance # Expose the logger instance if needed

def _format_float_for_log(value: Any, width: int, precision: int, default_na_width: Optional[int] = None) -> str:
    # ... (unchanged from provided version 1.0.0.7)
    if default_na_width is None: default_na_width = width
    actual_value = value
    if callable(value):
        try: actual_value = value()
        except Exception: actual_value = float('nan')
    if isinstance(actual_value, (int, float)) and not math.isnan(actual_value):
        return f"{actual_value:{width}.{precision}f}"
    return f"{'N/A':>{default_na_width}}"

def log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    # ... (unchanged from provided version 1.0.0.7, it correctly uses _shared_debug_rate_limiter)
    if not LOGGING_ENABLED or not ENABLE_DETAILED_PHYSICS_LOGS or not _platformer_logger_instance: return
    try:
        player_id_str = str(getattr(player, 'player_id', 'unknownP'))
        pos_x_val = getattr(player.pos, 'x', float('nan'))() if hasattr(player, 'pos') and hasattr(player.pos, 'x') and callable(getattr(player.pos, 'x')) else getattr(player.pos, 'x', float('nan')) if hasattr(player, 'pos') else float('nan')
        pos_y_val = getattr(player.pos, 'y', float('nan'))() if hasattr(player, 'pos') and hasattr(player.pos, 'y') and callable(getattr(player.pos, 'y')) else getattr(player.pos, 'y', float('nan')) if hasattr(player, 'pos') else float('nan')
        vel_x_val = getattr(player.vel, 'x', float('nan'))() if hasattr(player, 'vel') and hasattr(player.vel, 'x') and callable(getattr(player.vel, 'x')) else getattr(player.vel, 'x', float('nan')) if hasattr(player, 'vel') else float('nan')
        vel_y_val = getattr(player.vel, 'y', float('nan'))() if hasattr(player, 'vel') and hasattr(player.vel, 'y') and callable(getattr(player.vel, 'y')) else getattr(player.vel, 'y', float('nan')) if hasattr(player, 'vel') else float('nan')
        acc_x_val = getattr(player.acc, 'x', float('nan'))() if hasattr(player, 'acc') and hasattr(player.acc, 'x') and callable(getattr(player.acc, 'x')) else getattr(player.acc, 'x', float('nan')) if hasattr(player, 'acc') else float('nan')
        acc_y_val = getattr(player.acc, 'y', float('nan'))() if hasattr(player, 'acc') and hasattr(player.acc, 'y') and callable(getattr(player.acc, 'y')) else getattr(player.acc, 'y', float('nan')) if hasattr(player, 'acc') else float('nan')
        current_significant_data = (
            round(pos_x_val, 1) if not math.isnan(pos_x_val) else 'NaN', round(pos_y_val, 1) if not math.isnan(pos_y_val) else 'NaN',
            round(vel_x_val, 1) if not math.isnan(vel_x_val) else 'NaN', round(vel_y_val, 1) if not math.isnan(vel_y_val) else 'NaN',
            round(acc_x_val, 1) if not math.isnan(acc_x_val) else 'NaN', round(acc_y_val, 1) if not math.isnan(acc_y_val) else 'NaN',
            getattr(player, 'state', 'N/A'), getattr(player, 'on_ground', False), getattr(player, 'touching_wall', 0)
        )
        log_key_for_data_change = (player_id_str, message_tag)
        last_data = _last_physics_significant_data.get(log_key_for_data_change)
        data_has_changed = (last_data != current_significant_data)
        if data_has_changed:
            if _shared_debug_rate_limiter.can_proceed(_SHARED_DEBUG_LOG_KEY, period_sec=DEBUG_LOG_INTERVAL_SEC):
                pos_x_s = _format_float_for_log(pos_x_val, 6, 2); pos_y_s = _format_float_for_log(pos_y_val, 6, 2)
                vel_x_s = _format_float_for_log(vel_x_val, 5, 2); vel_y_s = _format_float_for_log(vel_y_val, 5, 2)
                acc_x_s = _format_float_for_log(acc_x_val, 4, 2); acc_y_s = _format_float_for_log(acc_y_val, 4, 2)
                state_s = str(getattr(player, 'state', 'N/A')); on_g_s = str(getattr(player, 'on_ground', 'N/A')); wall_t_s = str(getattr(player, 'touching_wall', 'N/A'))
                log_message = (f"P{player_id_str} PHYS-CHG: {message_tag:<18} | "
                               f"Pos:({pos_x_s},{pos_y_s}) Vel:({vel_x_s},{vel_y_s}) Acc:({acc_x_s},{acc_y_s}) "
                               f"State:{state_s} OnG:{on_g_s} WallT:{wall_t_s}")
                if isinstance(extra_info, str) and extra_info: log_message += f" | Extra: {extra_info}"
                elif isinstance(extra_info, (tuple, list)) and extra_info: log_message += f" | Extra: ({', '.join([str(item) for item in extra_info])})"
                _platformer_logger_instance.debug(log_message)
                _last_physics_significant_data[log_key_for_data_change] = current_significant_data
    except Exception as e:
        if _platformer_logger_instance:
            _platformer_logger_instance.error(f"Error in log_player_physics (P{getattr(player, 'player_id', '?')} tag '{message_tag}'): {e}", exc_info=False)
        else: sys.stderr.write(f"Error in log_player_physics (P{getattr(player, 'player_id', '?')} tag '{message_tag}'): {e}\n")

if _initialization_error_occurred:
    sys.stderr.write("PlatformerLogger: Logger setup encountered an error during initialization. Logging functionality may be impaired or using fallbacks.\n")

if __name__ == "__main__":
    if LOGGING_ENABLED and _platformer_logger_instance:
        info("Logger direct run: Info message 1.")
        debug("Logger direct run: Debug message 1 (should log).")
        debug("Logger direct run: Debug message 2 (should be rate-limited by shared limiter).")
        info("Logger direct run: Info message 2 (should log, not debug).")
        time.sleep(DEBUG_LOG_INTERVAL_SEC / 2)
        debug("Logger direct run: Debug message 3 (before interval, should be rate-limited).")
        print(f"Waiting for {DEBUG_LOG_INTERVAL_SEC}s...")
        time.sleep(DEBUG_LOG_INTERVAL_SEC)
        debug("Logger direct run: Debug message 4 (after interval, should log).")

        class MockQPointF:
            def __init__(self, x_val=0.0, y_val=0.0): self._x = x_val; self._y = y_val
            def x(self): return self._x
            def y(self): return self._y
        class MockPlayer:
            def __init__(self, player_id):
                self.player_id = player_id; self.pos = MockQPointF(10.0, 20.0); self.vel = MockQPointF(1.0, 0.5)
                self.acc = MockQPointF(0.0, 0.7); self.state = "idle"; self.on_ground = True; self.touching_wall = 0
        p1 = MockPlayer(1); p2 = MockPlayer(2)
        print(f"\n--- Testing log_player_physics with shared rate limit (expect 1 DEBUG log per {DEBUG_LOG_INTERVAL_SEC}s total) ---")
        if ENABLE_DETAILED_PHYSICS_LOGS:
            print(f"DEBUG_LOG_INTERVAL_SEC = {DEBUG_LOG_INTERVAL_SEC}")
            time.sleep(DEBUG_LOG_INTERVAL_SEC)
            debug("Generic debug before physics log (Msg 5, should log).")
            log_player_physics(p1, "PHYS_TEST_1", "Initial state P1 (should be rate-limited by above debug).")
            time.sleep(DEBUG_LOG_INTERVAL_SEC)
            log_player_physics(p1, "PHYS_TEST_2", "State P1 after wait (Msg 6, should log).")
            p1.pos = MockQPointF(10.5, 20.5)
            debug("Generic debug after physics log (should be rate-limited).")
            log_player_physics(p1, "PHYS_TEST_3", "Pos changed P1 (should be rate-limited, data changed but slot taken).")
            time.sleep(DEBUG_LOG_INTERVAL_SEC)
            log_player_physics(p1, "PHYS_TEST_4", "Pos changed P1 again (Msg 7, should log, data changed & slot free).")
            p2.pos = MockQPointF(50,50)
            log_player_physics(p2, "PHYS_TEST_P2_1", "Initial state P2 (should be rate-limited).")
        else: print("ENABLE_DETAILED_PHYSICS_LOGS is False. log_player_physics will not produce output (other than errors).")
        print(f"\nTest logs (if file logging enabled) likely written to: {LOG_FILE_PATH}")
        print("Check console output based on your CONSOLE_LEVEL settings.")
    else: print("Logging is globally disabled or logger instance failed to initialize. No log output from this direct run.")