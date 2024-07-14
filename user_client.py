from telethon import TelegramClient
from telethon.sessions import StringSession
import logging

logger = logging.getLogger(__name__)

class UserClient:
    def __init__(self):
        self.client = None

    async def start(self, api_id: int, api_hash: str, session_string: str = None):
        try:
            if session_string:
                self.client = TelegramClient(StringSession(session_string), api_id, api_hash)
            else:
                self.client = TelegramClient(StringSession(), api_id, api_hash)
            await self.client.start()
            logger.info("User client started successfully")
        except Exception as e:
            logger.error(f"Failed to start user client: {str(e)}")
            raise

    async def stop(self):
        if self.client:
            await self.client.disconnect()
            logger.info("User client stopped")

    def get_session_string(self):
        if self.client:
            return self.client.session.save()
        return None
