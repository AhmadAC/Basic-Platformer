# main_game/utils.py
# -*- coding: utf-8 -*-
"""
Utility classes and functions for the game.
Currently contains PrintLimiter.

Note: A similar RateLimiter class exists in main_game/logger.py.
Consider consolidating or using the logger.RateLimiter if more advanced
rate-limiting features are needed beyond simple print suppression.
"""

import time
import collections # For defaultdict
from typing import Dict, Optional

class PrintLimiter:
    """
    Limits the frequency of print statements or log messages for specific keys.
    Helps prevent console/log spam from repetitive events.
    """
    def __init__(self, default_limit: int = 1, default_period_sec: float = 1.0):
        """
        Initializes the PrintLimiter.

        Args:
            default_limit (int): Default number of times a message can be printed
                                 within the default_period_sec.
            default_period_sec (float): Default time window (in seconds) for the limit.
        """
        self.counts: Dict[str, int] = collections.defaultdict(int)
        self.timestamps: Dict[str, float] = collections.defaultdict(float)
        self.default_limit = default_limit
        self.default_period_sec = default_period_sec
        # self.globally_suppressed: Dict[str, bool] = {} # Unused in current logic

    def can_log(self, message_key: str, limit: Optional[int] = None, period_sec: Optional[float] = None) -> bool:
        """
        Checks if a log/print for the given message_key should proceed based on limits.

        Args:
            message_key (str): A unique key identifying the message type.
            limit (Optional[int]): Override the default limit for this specific key.
            period_sec (Optional[float]): Override the default period for this specific key.

        Returns:
            bool: True if the log/print should proceed, False otherwise.
        """
        limit_to_use = limit if limit is not None else self.default_limit
        period_to_use = period_sec if period_sec is not None else self.default_period_sec
        current_time = time.monotonic() # Use monotonic time for intervals

        last_period_start_time = self.timestamps[message_key] # defaultdict ensures key exists
        current_count_in_period = self.counts[message_key]   # defaultdict ensures key exists

        if current_time - last_period_start_time >= period_to_use:
            # Period has reset
            self.timestamps[message_key] = current_time
            self.counts[message_key] = 1 # This is the first log in the new period
            return True
        else:
            # Still within the current period
            if current_count_in_period < limit_to_use:
                self.counts[message_key] += 1
                return True
            else:
                # Limit reached for this period
                return False

    def can_log_strict_period(self, message_key: str, period_sec: Optional[float] = None) -> bool:
        """
        Strictly allows only one log per period. If a log occurs, the timer resets.
        This is different from `can_log` which allows a `limit` number of logs within a period.

        Args:
            message_key (str): A unique key identifying the message type.
            period_sec (Optional[float]): Override the default period for this specific key.

        Returns:
            bool: True if the log/print should proceed, False otherwise.
        """
        period_to_use = period_sec if period_sec is not None else self.default_period_sec
        current_time = time.monotonic()

        last_log_time = self.timestamps.get(message_key, 0.0) # Use .get for robust access

        if current_time - last_log_time >= period_to_use:
            self.timestamps[message_key] = current_time # Update timestamp on successful log
            self.counts[message_key] = 1 # Reset count for this key if using can_log elsewhere
            return True
        return False

    def reset_key(self, message_key: str):
        """Resets the count and timestamp for a specific message key."""
        if message_key in self.counts:
            del self.counts[message_key]
        if message_key in self.timestamps:
            del self.timestamps[message_key]

    def reset_all(self):
        """Resets counts and timestamps for all keys."""
        self.counts.clear()
        self.timestamps.clear()

# Example usage:
if __name__ == "__main__":
    limiter = PrintLimiter(default_limit=2, default_period_sec=1.0)

    print("Testing PrintLimiter (2 logs per 1 second per key):")
    key1 = "test_message_1"
    key2 = "test_message_2"

    for i in range(5):
        if limiter.can_log(key1):
            print(f"[{time.monotonic():.2f}] Logged for {key1} (Attempt {i+1})")
        else:
            print(f"[{time.monotonic():.2f}] Suppressed for {key1} (Attempt {i+1})")

        if limiter.can_log(key2, limit=1): # Override limit for key2
            print(f"[{time.monotonic():.2f}] Logged for {key2} with limit=1 (Attempt {i+1})")
        else:
            print(f"[{time.monotonic():.2f}] Suppressed for {key2} with limit=1 (Attempt {i+1})")
        
        if i == 1: # After 2 attempts
            print("...Waiting for 1.1 seconds to reset period...")
            time.sleep(1.1)

    print("\nTesting strict period limiter (1 log per 0.5 seconds per key):")
    strict_limiter = PrintLimiter(default_period_sec=0.5)
    for i in range(6):
        if strict_limiter.can_log_strict_period("strict_key"):
            print(f"[{time.monotonic():.2f}] Logged strict_key (Attempt {i+1})")
        else:
            print(f"[{time.monotonic():.2f}] Suppressed strict_key (Attempt {i+1})")
        time.sleep(0.2) # Sleep less than period