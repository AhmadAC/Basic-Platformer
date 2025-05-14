# utils.py
# -*- coding: utf-8 -*-
"""
Shared utility classes and functions.
version 1.0000000.1
"""
import time

class PrintLimiter:
    def __init__(self, default_limit=5, default_period=2.0):
        self.counts = {}
        self.timestamps = {}
        self.default_limit = default_limit
        self.default_period = default_period
        self.globally_suppressed = {} # Tracks if the "suppressing further prints" message was shown

    def can_print(self, message_key, limit=None, period=None):
        limit = limit if limit is not None else self.default_limit
        period = period if period is not None else self.default_period
        current_time = time.time()
        
        if message_key not in self.timestamps:
            self.timestamps[message_key] = current_time
            self.counts[message_key] = 0
            self.globally_suppressed[message_key] = False

        if current_time - self.timestamps[message_key] > period:
            self.timestamps[message_key] = current_time
            self.counts[message_key] = 0
            self.globally_suppressed[message_key] = False # Reset suppression message flag

        if self.counts[message_key] < limit:
            self.counts[message_key] += 1
            return True
        elif not self.globally_suppressed[message_key]: # Only print suppression message once per period
            # print(f"[PrintLimiter] Suppressing further prints for '{message_key}' for {period:.1f}s (limit: {limit})") # Keep this commented for less console noise
            self.globally_suppressed[message_key] = True
            return False
        return False