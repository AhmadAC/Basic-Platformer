# utils.py (PrintLimiter or a new LogLimiter class)
import time

class PrintLimiter: # Or rename to LogLimiter if you want a separate one
    def __init__(self, default_limit=1, default_period=1.0): # Changed defaults
        self.counts = {}
        self.timestamps = {}
        self.default_limit = default_limit
        self.default_period = default_period
        self.globally_suppressed = {}

    def can_log(self, message_key, limit=None, period=None): # Renamed for clarity
        limit = limit if limit is not None else self.default_limit
        period = period if period is not None else self.default_period
        current_time = time.time()

        if message_key not in self.timestamps:
            self.timestamps[message_key] = 0 # Initialize to allow first log
            self.counts[message_key] = 0
            self.globally_suppressed[message_key] = False

        if current_time - self.timestamps[message_key] >= period: # >= period allows the first log after period expires
            self.timestamps[message_key] = current_time
            self.counts[message_key] = 0 # Reset count for the new period
            self.globally_suppressed[message_key] = False
            return True # Allow logging

        # If still within the period, check the count limit
        if self.counts[message_key] < limit:
            # This part is tricky for strict "max 1 per second".
            # If a change happens 0.1s after the last log, but within the same second period,
            # and limit is 1, this won't allow it.
            # A simpler approach for "max 1 per second" is just to check the timestamp.
            # For now, let's assume the timestamp check is primary for "max 1 per second".
            # If you want to allow a burst of `limit` messages within a second, then reset, this is fine.
            # For "strictly no more than 1 log event of this type within a 1s window":
            # The current_time - self.timestamps[message_key] >= period check handles this.
            # We just need to update the timestamp if we *do* log.
            # The 'counts' logic here is more for "allow X logs within Y seconds".
            # For "max 1 log per second", the 'limit' should be 1.
            
            # Let's simplify for "max 1 log per second":
            # If the period hasn't passed, don't log.
            # If it has, log and update timestamp.
            # The `PrintLimiter` `can_print` needs a slight adjustment for this strictness if default_limit is > 1.
            # For your use case (max 1 log per second), `limit=1` and `period=1.0` is key.
            
            # If the period condition above was false (still within period):
            return False # Don't log, period not elapsed

        # This part regarding self.globally_suppressed is for console messages about suppression.
        # For file logging, you might not need the "suppressing further prints" message.

        # Fallback if logic is complex
        return False # Default to not logging if conditions aren't met

    # Simpler version for strict 1 log per second period.
    def can_log_strict_period(self, message_key, period=None):
        period = period if period is not None else self.default_period
        current_time = time.time()

        last_log_time = self.timestamps.get(message_key, 0)

        if current_time - last_log_time >= period:
            self.timestamps[message_key] = current_time # Update timestamp *when logging is allowed*
            return True
        return False