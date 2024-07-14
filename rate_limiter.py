# rate_limiter.py
import time
import asyncio
from collections import deque

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()

    async def wait(self):
        now = time.time()
        while len(self.calls) >= self.max_calls:
            sleep_time = self.calls[0] - (now - self.period)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            now = time.time()
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.popleft()
        self.calls.append(time.time())
