# file: utils.py
import logging
import asyncio
from telethon import events, Button
from auth import setup_auth_handlers
from forwarder import Forwarder
from database import db

logger = logging.getLogger(__name__)

def setup_commands(bot, user_client, forwarder: Forwarder):
    setup_auth_handlers(bot)

    @bot.on(events.NewMessage(pattern='/start_forwarding'))
    async def start_forwarding_command(event):
        try:
            await forwarder.start_forwarding(event, bot, db)
        except Exception as e:
            logger.error(f"Error in start_forwarding_command: {str(e)}")
            await event.reply(f"Error starting forwarding: {str(e)}")

    @bot.on(events.NewMessage(pattern='/stop_forwarding'))
    async def stop_forwarding_command(event):
        try:
            await forwarder.stop_forwarding(event, db)
        except Exception as e:
            logger.error(f"Error in stop_forwarding_command: {str(e)}")
            await event.reply(f"Error stopping forwarding: {str(e)}")

    @bot.on(events.NewMessage(pattern='/status'))
    async def status_command(event):
        try:
            await forwarder.status(event, db)
        except Exception as e:
            logger.error(f"Error in status_command: {str(e)}")
            await event.reply(f"Error retrieving status: {str(e)}")

    @bot.on(events.NewMessage(pattern='/help'))
    async def help_command(event):
        help_text = """
        Available commands:
        /start - Start the bot and begin authentication
        /help - Show this help message
        /start_forwarding <start_id>-<end_id> - Start or resume the forwarding process
        /stop_forwarding - Stop the forwarding process
        /status - Check the status of the forwarding process
        /retry_otp - Retry sending the OTP
        """
        await event.reply(
            help_text,
            buttons=[
                [Button.inline("Start Forwarding", b'start_forwarding')],
                [Button.inline("Stop Forwarding", b'stop_forwarding')],
                [Button.inline("Check Status", b'status')]
            ]
        )

    logger.info("Commands set up successfully")
