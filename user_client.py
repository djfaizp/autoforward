# user_client.py

import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio

logger = logging.getLogger(__name__)

class UserClient:
    def __init__(self):
        self.client = None

    async def start(self, api_id, api_hash, session_string=None):
        try:
            session = StringSession(session_string) if session_string else StringSession()
            self.client = TelegramClient(session, api_id, api_hash,
                                         device_model='MyApp', 
                                         system_version='1.0', 
                                         app_version='1.0', 
                                         lang_code='en')
            await self.client.start()
            logger.info("User client started successfully")
            await self.monitor_system_health()
        except Exception as e:
            logger.error(f"Failed to start user client: {str(e)}")
            raise

    async def stop(self):
        if self.client:
            await self.client.disconnect()
            logger.info("User client stopped")

    def get_session_string(self):
        return self.client.session.save() if self.client else None

    async def monitor_system_health(self):
        while True:
            memory_usage = self.get_memory_usage()
            queue_size = self.get_queue_size()
            logger.info(f"Memory usage: {memory_usage} MB")
            logger.info(f"Queue size: {queue_size} tasks")
            await asyncio.sleep(60)  # Adjust the monitoring interval as needed

    def get_memory_usage(self):
        # Placeholder for actual memory usage retrieval logic
        # Can be implemented using libraries such as psutil
        return 100  # Example value

    def get_queue_size(self):
        # Placeholder for actual queue size retrieval logic
        # This should interface with the actual task queue system used
        return 10  # Example value
