# logger.py
# version 1.0.0.3 (Added throttling for log_player_physics)
import logging
import os
import time # Added for robust timestamping

# --- GLOBAL LOGGING ENABLE/DISABLE SWITCH ---
LOGGING_ENABLED = True
# --- ---

# --- CONFIGURATION FOR DETAILED PHYSICS LOGS ---
ENABLE_DETAILED_PHYSICS_LOGS = True # This switch works with LOGGING_ENABLED
PHYSICS_LOG_INTERVAL_SEC = 1.0  # Log physics details at most once per this interval (per player)
_last_physics_log_time_by_player = {} # Stores last log timestamp for each player
# --- ---


LOG_FILENAME = "platformer_debug.log"
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILENAME)

_platformer_logger_instance = logging.getLogger("PlatformerLogger")

if LOGGING_ENABLED:
    _platformer_logger_instance.setLevel(logging.DEBUG)

    if os.path.exists(LOG_FILE_PATH):
        try:
            os.remove(LOG_FILE_PATH)
        except OSError as e:
            import sys
            sys.stderr.write(f"Warning: Could not delete old log file {LOG_FILE_PATH}: {e}\n")

    for handler in list(_platformer_logger_instance.handlers):
        _platformer_logger_instance.removeHandler(handler)
        handler.close()

    try:
        _file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w')
        _formatter = logging.Formatter("[%(asctime)s.%(msecs)03d] %(levelname)-7s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        # Changed formatter to include levelname and logger name for better context
        # _formatter = logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        _file_handler.setFormatter(_formatter)
        _platformer_logger_instance.addHandler(_file_handler)
        _platformer_logger_instance.propagate = False

        # Optional console handler for seeing logs directly
        # _console_handler = logging.StreamHandler()
        # _console_handler.setFormatter(_formatter) # Use the same formatter
        # _console_handler.setLevel(logging.DEBUG) # Set level for console output
        # _platformer_logger_instance.addHandler(_console_handler)

        _platformer_logger_instance.info(f"Logger initialized. Logging enabled. Output to: {LOG_FILE_PATH}")

    except Exception as e:
        import sys
        sys.stderr.write(f"CRITICAL ERROR: Failed to initialize file logger at {LOG_FILE_PATH}: {e}\n")
        sys.stderr.write(f"CRITICAL ERROR: PlatformerLogger will not write to file, despite LOGGING_ENABLED=True.\n")
        for handler in list(_platformer_logger_instance.handlers):
            _platformer_logger_instance.removeHandler(handler)
            handler.close()
        _platformer_logger_instance.addHandler(logging.NullHandler())
        _platformer_logger_instance.propagate = False
else:
    for handler in list(_platformer_logger_instance.handlers):
        _platformer_logger_instance.removeHandler(handler)
        handler.close()
    _platformer_logger_instance.addHandler(logging.NullHandler())
    _platformer_logger_instance.setLevel(logging.CRITICAL + 1) # Effectively disable
    _platformer_logger_instance.propagate = False
    # print("INFO: PlatformerLogger is disabled by configuration.")


def log_player_physics(player, message_tag, extra_info=""):
    """Helper to log player physics details if detailed logging is enabled, with throttling."""
    if not LOGGING_ENABLED or not ENABLE_DETAILED_PHYSICS_LOGS:
        return

    try:
        # Determine a unique identifier for the player for throttling
        # Ensure player_id is a string or a consistently hashable type.
        # Using a prefix "player_" to avoid potential collisions if player_id could be an int like 0 or 1.
        player_throttle_id = f"player_{str(getattr(player, 'player_id', 'unknown'))}"
        current_time_sec = time.time()

        # --- Throttling Logic ---
        last_log_time = _last_physics_log_time_by_player.get(player_throttle_id, 0.0)
        if current_time_sec - last_log_time < PHYSICS_LOG_INTERVAL_SEC:
            return  # Throttled, do not log for this player yet

        # If not throttled, update the last log time for this player *before* formatting
        # to reduce chance of multiple logs if formatting is slow (unlikely but good practice).
        _last_physics_log_time_by_player[player_throttle_id] = current_time_sec
        # --- End Throttling Logic ---

        # Formatting logic (existing code)
        player_id_str_msg = str(getattr(player, 'player_id', 'P?')) # For the message content
        pos_x = getattr(player, 'pos', type('obj', (object,), {'x': float('nan')})).x
        pos_y = getattr(player, 'pos', type('obj', (object,), {'y': float('nan')})).y
        vel_x = getattr(player, 'vel', type('obj', (object,), {'x': float('nan')})).x
        vel_y = getattr(player, 'vel', type('obj', (object,), {'y': float('nan')})).y
        player_rect_str = str(getattr(player, 'rect', 'N/A'))
        player_on_ground = getattr(player, 'on_ground', 'N/A')
        player_state = getattr(player, 'state', 'N/A')
        player_acc_x = getattr(player, 'acc', type('obj', (object,), {'x': float('nan')})).x
        player_acc_y = getattr(player, 'acc', type('obj', (object,), {'y': float('nan')})).y
        player_wall_touch = getattr(player, 'touching_wall', 'N/A')

        log_msg_parts = [
            f"P{player_id_str_msg} PHYS: {message_tag: <18} | "
            f"Pos:({pos_x:6.2f},{pos_y:6.2f}) "
            f"Vel:({vel_x:5.2f},{vel_y:5.2f}) "
        ]

        if message_tag == "UPDATE_START":
             log_msg_parts.append(
                f"Acc:({player_acc_x:4.2f},{player_acc_y:4.2f}) "
                f"Rect:{player_rect_str} OnGround:{player_on_ground} State:{player_state}"
             )
        elif "PLAT_COLL_CHECK" in message_tag:
            player_r_str, plat_r_str, plat_t = "N/A", "N/A", "N/A"
            if isinstance(extra_info, tuple) and len(extra_info) == 3:
                player_r_str, plat_r_str, plat_t = str(extra_info[0]), str(extra_info[1]), str(extra_info[2])
            log_msg_parts.append(
                f"PlayerRect:{player_r_str} | PlatRect:{plat_r_str} | PlatType:{plat_t}"
            )
        elif "PLAT_COLL_RESOLVED" in message_tag:
            snap_r_str, orig_r_str, n_pos_str, n_vel_axis_val_str, n_og_str, axis_char = "N/A", "N/A", "N/A", "N/A", "N/A", "?"
            if isinstance(extra_info, tuple) and len(extra_info) == 6:
                snap_r_str, orig_r_str = str(extra_info[0]), str(extra_info[1])
                n_pos_x, n_pos_y = extra_info[2]
                n_pos_str = f"({n_pos_x:.2f},{n_pos_y:.2f})"
                n_vel_axis_val_str = f"{extra_info[3]:.2f}"
                n_og_str = str(extra_info[4])
                axis_char = str(extra_info[5])
            log_msg_parts.append(
                f"SnappedRect:{snap_r_str} (from {orig_r_str}) | "
                f"NewPos:{n_pos_str} | Vel.{axis_char}:{n_vel_axis_val_str} OnGround:{n_og_str}"
            )
        elif "CHAR_COLL_CHECK" in message_tag:
            player_r_str, other_r_str, other_id_str = "N/A", "N/A", "N/A"
            if isinstance(extra_info, tuple) and len(extra_info) == 3:
                player_r_str, other_r_str, other_id_str = str(extra_info[0]), str(extra_info[1]), str(extra_info[2])
            log_msg_parts.append(
                f"PlayerRect:{player_r_str} | OtherRect:{other_r_str} | OtherID:{other_id_str}"
            )
        elif "CHAR_COLL_RESOLVED" in message_tag:
            snap_r_str, orig_r_str, n_pos_str, n_vel_axis_val_str, axis_char = "N/A", "N/A", "N/A", "N/A", "?"
            if isinstance(extra_info, tuple) and len(extra_info) == 5:
                snap_r_str, orig_r_str = str(extra_info[0]), str(extra_info[1])
                n_pos_x, n_pos_y = extra_info[2]
                n_pos_str = f"({n_pos_x:.2f},{n_pos_y:.2f})"
                n_vel_axis_val_str = f"{extra_info[3]:.2f}"
                axis_char = str(extra_info[4])
            log_msg_parts.append(
                f"SnappedRect:{snap_r_str} (from {orig_r_str}) | "
                f"NewPos:{n_pos_str} | Vel.{axis_char}:{n_vel_axis_val_str}"
            )
        elif "PLAT_COLL_DONE" in message_tag:
            axis_char = "x" if "X_" in message_tag else "y"
            pos_axis_val = pos_x if axis_char == 'x' else pos_y
            vel_axis_val = vel_x if axis_char == 'x' else vel_y
            rect_midbottom_str = str(player.rect.midbottom) if hasattr(player,'rect') and hasattr(player.rect, 'midbottom') else 'N/A'
            if axis_char == "x": log_msg_parts.append(f"Pos.{axis_char}:{pos_axis_val:6.2f} | Rect.midbottom:{rect_midbottom_str} | Vel.{axis_char}:{vel_axis_val:5.2f} WallTouch:{player_wall_touch}")
            else: log_msg_parts.append(f"Pos.{axis_char}:{pos_axis_val:6.2f} | Rect.midbottom:{rect_midbottom_str} | Vel.{axis_char}:{vel_axis_val:5.2f} OnGround:{player_on_ground}")
        elif "FINAL_POS_SYNC" in message_tag: log_msg_parts.append(f"Pos:({pos_x:6.2f},{pos_y:6.2f}) | Rect.midbottom: {player_rect_str}") # player_rect_str is already player.rect
        elif "UPDATE_END" in message_tag: log_msg_parts.append(f"Pos:({pos_x:6.2f},{pos_y:6.2f}) Vel:({vel_x:5.2f},{vel_y:5.2f}) OnGround:{player_on_ground} State:{player_state}")
        
        if isinstance(extra_info, str) and extra_info and not any(kw in message_tag for kw in ["PLAT_COLL_CHECK", "PLAT_COLL_RESOLVED", "CHAR_COLL_CHECK", "CHAR_COLL_RESOLVED", "PLAT_COLL_DONE", "FINAL_POS_SYNC", "UPDATE_END", "UPDATE_START"]):
            log_msg_parts.append(f" {extra_info}")
            
        _platformer_logger_instance.debug("".join(log_msg_parts))
    except Exception as e:
        # Get player_id again for error message, or use a default if it fails early
        err_player_id = 'unknown_player'
        try:
            err_player_id = f"P{str(getattr(player, 'player_id', '?'))}"
        except: #pylint: disable=bare-except
            pass # Keep err_player_id as 'unknown_player'
        _platformer_logger_instance.error(f"Error in log_player_physics for {err_player_id} tag '{message_tag}': {e}", exc_info=False) # exc_info=False to prevent huge tracebacks for simple formatting errors. Set to True if needed.

logger = _platformer_logger_instance

# Expose logging functions directly
def debug(message, *args, **kwargs):
    if LOGGING_ENABLED:
        _platformer_logger_instance.debug(message, *args, **kwargs)

def info(message, *args, **kwargs):
    if LOGGING_ENABLED:
        _platformer_logger_instance.info(message, *args, **kwargs)

def warning(message, *args, **kwargs):
    if LOGGING_ENABLED:
        _platformer_logger_instance.warning(message, *args, **kwargs)

def error(message, *args, **kwargs):
    if LOGGING_ENABLED:
        _platformer_logger_instance.error(message, *args, **kwargs)

def critical(message, *args, **kwargs):
    if LOGGING_ENABLED:
        _platformer_logger_instance.critical(message, *args, **kwargs)

if __name__ == "__main__":
    if LOGGING_ENABLED:
        info("This is an info message from logger.py direct run.")
        debug("This is a debug message from logger.py direct run.")
        
        # Mock player for testing log_player_physics
        class MockPlayer:
            def __init__(self, player_id):
                self.player_id = player_id
                self.pos = type('obj', (object,), {'x': 10.0, 'y': 20.0})
                self.vel = type('obj', (object,), {'x': 1.0, 'y': -1.0})
                self.rect = type('obj', (object,), {'midbottom': (15,30)}) # Mocking rect enough for one case
                self.on_ground = True
                self.state = "idle"
                self.acc = type('obj', (object,), {'x': 0.0, 'y': 0.0})
                self.touching_wall = 0

        player1 = MockPlayer(1)
        player2 = MockPlayer("Alpha")

        print(f"Testing throttled physics logs (interval: {PHYSICS_LOG_INTERVAL_SEC}s). Output may be sparse.")
        for i in range(5): # Try to log 5 times in quick succession
            log_player_physics(player1, "UPDATE_START", f"Loop {i}")
            log_player_physics(player2, "UPDATE_START", f"Loop {i}")
            if i < 4: # Don't sleep on the last iteration
                time.sleep(0.3) # Sleep less than interval to test throttling

        time.sleep(PHYSICS_LOG_INTERVAL_SEC + 0.1) # Sleep longer than interval
        log_player_physics(player1, "UPDATE_END", "After long sleep")
        log_player_physics(player2, "UPDATE_END", "After long sleep")

        print(f"Test logs (if enabled) written to {LOG_FILE_PATH}")
    else:
        print("Logging is disabled. No log file generated from this direct run.")