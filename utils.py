#################### START OF FILE: utils.py ####################

# utils.py
import time
import collections # For defaultdict

class PrintLimiter:
    def __init__(self, default_limit=1, default_period=1.0):
        self.counts = collections.defaultdict(int) # Use defaultdict for cleaner initialization
        self.timestamps = collections.defaultdict(float) # Use defaultdict
        self.default_limit = default_limit
        self.default_period = default_period
        # self.globally_suppressed = {} # This was unused in the provided can_log logic

    def can_log(self, message_key, limit=None, period=None):
        limit_to_use = limit if limit is not None else self.default_limit
        period_to_use = period if period is not None else self.default_period
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

    def can_log_strict_period(self, message_key, period=None): # Kept as is
        period = period if period is not None else self.default_period
        current_time = time.monotonic() # Use monotonic for consistency

        last_log_time = self.timestamps.get(message_key, 0.0) # Use .get for robust access

        if current_time - last_log_time >= period:
            self.timestamps[message_key] = current_time
            return True
        return False

#################### END OF FILE: utils.py ####################