# bot_client.py
import logging
from telethon import TelegramClient

logger = logging.getLogger(__name__)

class BotClient(TelegramClient):
    def __init__(self, config):
        super().__init__('bot', config.API_ID, config.API_HASH)
        self.bot_token = config.BOT_TOKEN

    async def start(self):
        try:
            await super().start(bot_token=self.bot_token)
            logger.info("Bot client started successfully")
        except Exception as e:
            logger.error(f"Unexpected error starting bot client: {str(e)}", exc_info=True)
            raise

    async def stop(self):
        try:
            await self.disconnect()
            logger.info("Bot client stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot client: {str(e)}")