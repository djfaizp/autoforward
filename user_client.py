# user_client.py
from telethon import TelegramClient
from telethon.sessions import StringSession
import logging

logger = logging.getLogger(__name__)

class UserClient:
    def __init__(self):
        self.client = None

    async def start(self, api_id, api_hash, session_string=None):
        try:
            session = StringSession(session_string) if session_string else StringSession()
            self.client = TelegramClient(session, api_id, api_hash)
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
        return self.client.session.save() if self.client else None
