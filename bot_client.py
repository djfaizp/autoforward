# file: bot_client.py
import logging
from telethon import TelegramClient, events

logger = logging.getLogger(__name__)

class BotClient(TelegramClient):
    def __init__(self, config):
        super().__init__('bot', config.API_ID, config.API_HASH, 
                         device_model='MyApp', 
                         system_version='1.0', 
                         app_version='1.0', 
                         lang_code='en')
        self.bot_token = config.BOT_TOKEN
        self.config = config
        self.me = None
        self.username = None

    async def start(self):
        try:
            await super().start(bot_token=self.bot_token)
            self.me = await self.get_me()
            self.username = self.me.username
            logger.info(f"Bot started as @{self.username}")
        except Exception as e:
            logger.error(f"Unexpected error starting bot client: {str(e)}", exc_info=True)
            raise

    async def stop(self):
        try:
            await self.disconnect()
            logger.info("Bot client stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot client: {str(e)}")

    def add_event_handler(self, callback, event):
        super().add_event_handler(callback, event)
        logger.info(f"Added event handler for {event.__class__.__name__}")

    async def send_message(self, chat_id, message, **kwargs):
        try:
            return await super().send_message(chat_id, message, **kwargs)
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            raise

    async def edit_message(self, chat_id, message_id, new_message, **kwargs):
        try:
            return await super().edit_message(chat_id, message_id, new_message, **kwargs)
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            raise
