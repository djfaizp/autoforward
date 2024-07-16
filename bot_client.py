# bot_client.py
import asyncio
from telethon import TelegramClient
import logging
from typing import Any

logger = logging.getLogger(__name__)

class BotClient(TelegramClient):
    def __init__(self, config: Any):
        super().__init__('bot', config.API_ID, config.API_HASH)
        self.bot_token = config.BOT_TOKEN

    async def start(self):
        try:
            await super().start(bot_token=self.bot_token)
            logger.info("Bot client started successfully")
        except asyncio.CancelledError:
            logger.info("Bot client start was cancelled")
            raise
        except ValueError as ve:
            logger.error(f"ValueError in starting bot client: {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error starting bot client: {str(e)}")
            raise

    async def stop(self):
        try:
            await self.disconnect()
            logger.info("Bot client stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot client: {str(e)}")

    async def handle_message(self, event):
        try:
            await event.reply("I received your message. How can I help you?")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await event.reply("An error occurred while processing your request.")
