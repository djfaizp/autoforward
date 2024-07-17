# rate_limiter.py
import asyncio
import time
from collections import defaultdict, deque

class UserRateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.user_calls = defaultdict(deque)

    async def wait(self, user_id):
        now = time.time()
        user_queue = self.user_calls[user_id]
        
        while len(user_queue) >= self.max_calls:
            sleep_time = user_queue[0] - (now - self.period)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            now = time.time()
            while user_queue and user_queue[0] <= now - self.period:
                user_queue.popleft()
        
        user_queue.append(time.time())
