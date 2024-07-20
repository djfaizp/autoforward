# rate_limiter.py

import asyncio
import time
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

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
                logger.info(f"Rate limit exceeded for user {user_id}. Sleeping for {sleep_time:.2f} seconds.")
                await asyncio.sleep(sleep_time)
            now = time.time()
            while user_queue and user_queue[0] <= now - self.period:
                user_queue.popleft()
        
        user_queue.append(time.time())

    async def exponential_backoff(self, base_delay, max_delay, factor=2):
        delay = base_delay
        while delay < max_delay:
            logger.info(f"Retrying after {delay:.2f} seconds...")
            await asyncio.sleep(delay)
            delay *= factor
        logger.info(f"Max delay {max_delay:.2f} seconds reached. No further retries.")

    def get_rate_limit_status(self):
        rate_limit_status = {user_id: len(calls) for user_id, calls in self.user_calls.items()}
        logger.info(f"Current rate limit status: {rate_limit_status}")
        return rate_limit_status
