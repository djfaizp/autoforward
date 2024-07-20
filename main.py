# main.py

import asyncio
import logging
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

        setup_commands(bot, user_client, forwarder)
        logger.info("Commands set up successfully")

        active_users = await db.get_active_users()
        logger.info(f"Active users: {active_users}")

        tasks = [forwarder.process_user_queue(user_id, bot, db, None) for user_id in active_users]
        logger.info(f"Created {len(tasks)} tasks for active users")
        
        # Start the forwarding worker
        worker_task = asyncio.create_task(forwarder.worker())
        
        # Start system health monitoring
        health_task = asyncio.create_task(monitor_system_health())

        await asyncio.gather(*tasks, worker_task, health_task)
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

async def monitor_system_health():
    while True:
        mem = virtual_memory()
        logger.info(f"Memory usage: {mem.percent}% used")
        await asyncio.sleep(60)  # Adjust the monitoring interval as needed

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        
