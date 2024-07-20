# file: main.py
import asyncio
import logging
import os
import shutil
from bot_client import BotClient
from user_client import UserClient
from forwarder import Forwarder
from config import load_config
from database import db
from utils import setup_commands

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('telethon.network.mtprotosender').setLevel(logging.WARNING)
logging.getLogger('telethon.network.connection.connection').setLevel(logging.WARNING)

def clear_cache():
    """Clear Python cache by removing .pyc files and __pycache__ directories."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, files in os.walk(current_dir):
        for dir in dirs:
            if dir == "__pycache__":
                cache_dir = os.path.join(root, dir)
                logger.info(f"Removing cache directory: {cache_dir}")
                shutil.rmtree(cache_dir)
        for file in files:
            if file.endswith(".pyc"):
                cache_file = os.path.join(root, file)
                logger.info(f"Removing cache file: {cache_file}")
                os.remove(cache_file)

async def main():
    bot = None
    user_client = None
    try:
        logger.info("Clearing Python cache...")
        clear_cache()
        logger.info("Cache cleared successfully")

        config = load_config()
        logger.info("Configuration loaded successfully")
        
        await db.connect()
        logger.info("Connected to MongoDB")

        bot = BotClient(config)
        await bot.start()
        logger.info("Bot client started successfully")

        user_client = UserClient()
        forwarder = Forwarder(user_client, db, config)

        # Set up commands
        setup_commands(bot, user_client, forwarder)
        logger.info("Commands set up successfully")

        active_users = await db.get_active_users()
        logger.info(f"Active users: {active_users}")

        tasks = [forwarder.process_user_queue(user_id, bot, db, None) for user_id in active_users]
        logger.info(f"Created {len(tasks)} tasks for active users")
        
        worker_task = asyncio.create_task(forwarder.worker())

        # Run the bot and other tasks concurrently
        await asyncio.gather(bot.run_until_disconnected(), *tasks, worker_task)
        logger.info("All tasks have been processed")

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
