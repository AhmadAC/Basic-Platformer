# logger.py
## version 1.0.0.1 
import logging
import os
from datetime import datetime
# import pygame # Add if log_player_physics uses pygame.Rect or other pygame types directly for formatting

LOG_FILENAME = "platformer_debug.log"
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILENAME)

# Renamed to avoid conflict if other modules also name their logger 'logger'
# This is the actual logging object.
_platformer_logger_instance = logging.getLogger("PlatformerLogger") 
_platformer_logger_instance.setLevel(logging.DEBUG) # Set level on the instance

# Setup handlers if not already configured (e.g. by basicConfig)
if not _platformer_logger_instance.hasHandlers():
    _file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w')
    _formatter = logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    _file_handler.setFormatter(_formatter)
    _platformer_logger_instance.addHandler(_file_handler)

    # If you also want console output for debugging the logger itself:
    # _console_handler = logging.StreamHandler()
    # _console_handler.setFormatter(_formatter)
    # _platformer_logger_instance.addHandler(_console_handler)


# --- CONFIGURATION FOR DETAILED PHYSICS LOGS ---
ENABLE_DETAILED_PHYSICS_LOGS = True 
# --- ---

def log_player_physics(player, message_tag, extra_info=""):
    """Helper to log player physics details if detailed logging is enabled."""
    if not ENABLE_DETAILED_PHYSICS_LOGS:
        return

    try:
        # Ensure player has necessary attributes before trying to access them
        player_id_str = str(getattr(player, 'player_id', 'P?'))
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


        log_msg = (
            f"P{player_id_str} PHYS: {message_tag: <18} | "
            f"Pos:({pos_x:6.2f},{pos_y:6.2f}) "
            f"Vel:({vel_x:5.2f},{vel_y:5.2f}) "
        )
        if message_tag == "UPDATE_START":
             log_msg += (
                f"Acc:({player_acc_x:4.2f},{player_acc_y:4.2f}) "
                f"Rect:{player_rect_str} OnGround:{player_on_ground} State:{player_state}"
             )
        elif "PLAT_COLL_CHECK" in message_tag:
            player_r_str, plat_r_str, plat_t = "N/A", "N/A", "N/A"
            if isinstance(extra_info, tuple) and len(extra_info) == 3:
                player_r_str, plat_r_str, plat_t = str(extra_info[0]), str(extra_info[1]), str(extra_info[2])
            log_msg += (
                f"PlayerRect:{player_r_str} | PlatRect:{plat_r_str} | PlatType:{plat_t}"
            )
        elif "PLAT_COLL_RESOLVED" in message_tag: # General for X or Y
            snap_r_str, orig_r_str, n_pos_str, n_vel_axis_val_str, n_og_str, axis_char = "N/A", "N/A", "N/A", "N/A", "N/A", "?"
            if isinstance(extra_info, tuple) and len(extra_info) == 6:
                snap_r_str, orig_r_str = str(extra_info[0]), str(extra_info[1])
                n_pos_x, n_pos_y = extra_info[2]
                n_pos_str = f"({n_pos_x:.2f},{n_pos_y:.2f})"
                n_vel_axis_val_str = f"{extra_info[3]:.2f}"
                n_og_str = str(extra_info[4])
                axis_char = str(extra_info[5])
            log_msg += (
                f"SnappedRect:{snap_r_str} (from {orig_r_str}) | "
                f"NewPos:{n_pos_str} | Vel.{axis_char}:{n_vel_axis_val_str} OnGround:{n_og_str}"
            )
        elif "CHAR_COLL_CHECK" in message_tag:
            player_r_str, other_r_str, other_id_str = "N/A", "N/A", "N/A"
            if isinstance(extra_info, tuple) and len(extra_info) == 3:
                player_r_str, other_r_str, other_id_str = str(extra_info[0]), str(extra_info[1]), str(extra_info[2])
            log_msg += (
                f"PlayerRect:{player_r_str} | OtherRect:{other_r_str} | OtherID:{other_id_str}"
            )
        elif "CHAR_COLL_RESOLVED" in message_tag: # General for X or Y
            snap_r_str, orig_r_str, n_pos_str, n_vel_axis_val_str, axis_char = "N/A", "N/A", "N/A", "N/A", "?"
            if isinstance(extra_info, tuple) and len(extra_info) == 5:
                snap_r_str, orig_r_str = str(extra_info[0]), str(extra_info[1])
                n_pos_x, n_pos_y = extra_info[2]
                n_pos_str = f"({n_pos_x:.2f},{n_pos_y:.2f})"
                n_vel_axis_val_str = f"{extra_info[3]:.2f}"
                axis_char = str(extra_info[4])
            log_msg += (
                f"SnappedRect:{snap_r_str} (from {orig_r_str}) | "
                f"NewPos:{n_pos_str} | Vel.{axis_char}:{n_vel_axis_val_str}"
            )

        elif "PLAT_COLL_DONE" in message_tag: 
            axis_char = "x" if "X_" in message_tag else "y"
            pos_axis_val = pos_x if axis_char == 'x' else pos_y
            vel_axis_val = vel_x if axis_char == 'x' else vel_y
            if axis_char == "x": log_msg += (f"Pos.{axis_char}: {pos_axis_val:6.2f} | Rect.midbottom: {player.rect.midbottom if hasattr(player,'rect') else 'N/A'} | Vel.{axis_char}: {vel_axis_val:5.2f} WallTouch:{player_wall_touch}")
            else: log_msg += (f"Pos.{axis_char}: {pos_axis_val:6.2f} | Rect.midbottom: {player.rect.midbottom if hasattr(player,'rect') else 'N/A'} | Vel.{axis_char}: {vel_axis_val:5.2f} OnGround:{player_on_ground}")
        elif "FINAL_POS_SYNC" in message_tag: log_msg += (f"Pos:({pos_x:6.2f},{pos_y:6.2f}) | Rect.midbottom: {player_rect_str}")
        elif "UPDATE_END" in message_tag: log_msg += (f"Pos:({pos_x:6.2f},{pos_y:6.2f}) Vel:({vel_x:5.2f},{vel_y:5.2f}) OnGround:{player_on_ground} State:{player_state}")
        
        if isinstance(extra_info, str) and extra_info and not any(kw in message_tag for kw in ["PLAT_COLL_CHECK", "PLAT_COLL_RESOLVED", "CHAR_COLL_CHECK", "CHAR_COLL_RESOLVED", "PLAT_COLL_DONE", "FINAL_POS_SYNC", "UPDATE_END", "UPDATE_START"]):
            log_msg += f" {extra_info}"
            
        _platformer_logger_instance.debug(log_msg)
    except Exception as e:
        _platformer_logger_instance.error(f"Error in log_player_physics for {message_tag}: {e}")


# Make the logger instance available for import by other modules
logger = _platformer_logger_instance 

# Expose logging functions directly
def debug(message):
    _platformer_logger_instance.debug(message)

def info(message):
    _platformer_logger_instance.info(message)

def warning(message):
    _platformer_logger_instance.warning(message)

def error(message):
    _platformer_logger_instance.error(message)

def critical(message):
    _platformer_logger_instance.critical(message)

if not _platformer_logger_instance.handlers: # Check if handlers were already added by basicConfig in another module
    # This case should ideally not happen if logger.py is the first to configure this named logger.
    # If it does, it means another module might have called logging.basicConfig() which affects the root logger,
    # and potentially named loggers if they propagate. Best practice is to configure specific loggers.
    info("Logger instance didn't have handlers, re-adding file handler (this might indicate an issue).")
    _file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w')
    _formatter = logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    _file_handler.setFormatter(_formatter)
    _platformer_logger_instance.addHandler(_file_handler)

info(f"Logger initialized (or re-confirmed). Logging to: {LOG_FILE_PATH}")

if __name__ == "__main__":
    info("This is an info message from logger.py direct run.")
    debug("This is a debug message from logger.py direct run.")
    print(f"Test logs written to {LOG_FILE_PATH}")