import asyncio
import logging
from bot_client import BotClient
from user_client import UserClient
from commands import setup_commands
from forwarder import Forwarder
from config import Settings  # Adjusted import to match existing config structure
from database import db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set logging level for specific telethon modules to WARNING to suppress DEBUG messages
logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('telethon.network.mtprotosender').setLevel(logging.WARNING)
logging.getLogger('telethon.network.connection.connection').setLevel(logging.WARNING)

async def main():
    bot = None
    user_client = None
    try:
        config = Settings()  # Directly instantiate Settings
        logger.info("Configuration loaded successfully")
        
        await db.connect()
        logger.info("Connected to database")

        await db.setup_message_queue()  # Ensure the database setup is called

        bot = BotClient(config)
        await bot.start()
        logger.info("Bot client started successfully")

        user_client = UserClient()

        forwarder = Forwarder(user_client, db, config)  # Pass config to Forwarder

        setup_commands(bot, user_client, forwarder, db)
        logger.info("Commands set up successfully")

        logger.info("Bot is now running")
        await bot.run_until_disconnected()
    except asyncio.CancelledError:
        logger.info("Main task was cancelled.")
    except Exception as e:
        logger.error(f"An error occurred in main: {str(e)}", exc_info=True)
    finally:
        if bot:
            await bot.disconnect()
        if user_client and user_client.client:
            await user_client.stop()
        await db.disconnect()
        logger.info("Bot has been disconnected and database connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
