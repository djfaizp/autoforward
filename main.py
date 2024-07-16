import asyncio
import logging
from bot_client import BotClient
from user_client import UserClient
from commands import setup_commands
from forwarder import Forwarder
from config import load_config
from database import db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('telethon.network.mtprotosender').setLevel(logging.WARNING)
logging.getLogger('telethon.network.connection.connection').setLevel(logging.WARNING)

async def main():
    bot = None
    user_client = None
    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
        
        await db.connect()
        logger.info("Connected to MongoDB")

        bot = BotClient(config)
        await bot.start()
        logger.info("Bot client started successfully")

        user_client = UserClient()
        forwarder = Forwarder(user_client, db, config)

        setup_commands(bot, user_client, forwarder, db)
        logger.info("Commands set up successfully")

        active_users = await db.get_active_users()
        logger.info(f"Active users: {active_users}")

        tasks = [forwarder.process_user_queue(user_id, bot, db, None) for user_id in active_users]
        logger.info(f"Created {len(tasks)} tasks for active users")
        
        await asyncio.gather(*tasks)
        logger.info("All tasks have been processed")

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
