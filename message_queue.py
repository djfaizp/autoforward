import asyncio
from typing import Any, Dict

from database import Database

class MessageQueue:
    def __init__(self, db: Database):
        self.db = db
        self.queue = asyncio.Queue()

    async def enqueue(self, message: Dict[str, Any]):
        await self.queue.put(message)

    async def dequeue(self):
        return await self.queue.get()

    async def process_queue(self, worker_func, num_workers=10):
        tasks = [asyncio.create_task(worker_func(self.queue)) for _ in range(num_workers)]
        await asyncio.gather(*tasks)
