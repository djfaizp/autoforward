import asyncio
import time

class UserRateLimiter:
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self.user_limits = {}

    async def wait(self, user_id: int):
        if user_id not in self.user_limits:
            self.user_limits[user_id] = []
        while len(self.user_limits[user_id]) >= self.max_calls:
            await asyncio.sleep(self.period)
            self.user_limits[user_id] = [t for t in self.user_limits[user_id] if t > time.time() - self.period]
        self.user_limits[user_id].append(time.time())
