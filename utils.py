# file: utils.py
import logging
from telethon import events, Button
from auth import (
    start_auth,
    handle_auth as auth_handler,
    handle_retry_otp,
    AuthState
)
from database import db
from forwarder import Forwarder

logger = logging.getLogger(__name__)

def setup_commands(bot, user_client, forwarder: Forwarder):
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_command(event):
        user_id = event.sender_id
        if not is_valid_user_id(user_id):
            logger.info(f"Invalid user ID {user_id}. Skipping auth process.")
            return

        user_data = await db.get_user_credentials(user_id)
        if not user_data or not user_data.get('session_string'):
            await start_auth(event, user_id)
        else:
            await event.reply(
                "Welcome back! You are already authenticated. Use /help to see available commands.",
                buttons=[Button.inline("Help", b'help')]
            )
        logger.info(f"User data for user {user_id}: {user_data}")

    @bot.on(events.NewMessage(pattern=r'^(?!/start|/help|/start_forwarding|/stop_forwarding|/status|/retry_otp)'))
    async def handle_auth_message(event):
        await auth_handler(event)

    @bot.on(events.NewMessage(pattern='/start_forwarding'))
    async def start_forwarding_command(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)

        if not user_data or not user_data.get('session_string'):
            await event.reply("You are not authenticated. Please start with /start")
            return

        try:
            await forwarder.start_forwarding(event, bot, db)
            await event.reply("Message forwarding started.")
        except Exception as e:
            logger.error(f"Error in start_forwarding_command: {str(e)}")
            await event.reply(f"Error starting forwarding: {str(e)}")

    @bot.on(events.NewMessage(pattern='/stop_forwarding'))
    async def stop_forwarding_command(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)

        if not user_data or not user_data.get('session_string'):
            await event.reply("You are not authenticated. Please start with /start")
            return

        try:
            await forwarder.stop_forwarding(event, db)
            await event.reply("Message forwarding stopped.")
        except Exception as e:
            logger.error(f"Error in stop_forwarding_command: {str(e)}")
            await event.reply(f"Error stopping forwarding: {str(e)}")

    @bot.on(events.NewMessage(pattern='/status'))
    async def status_command(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)

        if not user_data or not user_data.get('session_string'):
            await event.reply("You are not authenticated. Please start with /start")
            return

        try:
            status = await forwarder.status(event, db)
            await event.reply(f"Forwarding status: {status}")
        except Exception as e:
            logger.error(f"Error in status_command: {str(e)}")
            await event.reply(f"Error retrieving status: {str(e)}")

    @bot.on(events.NewMessage(pattern='/help'))
    async def help_command(event):
        help_text = """
        Available commands:
        /start - Start the bot and begin authentication
        /help - Show this help message
        /start_forwarding - Start or resume the forwarding process
        /stop_forwarding - Stop the forwarding process
        /status - Check the status of the forwarding process
        /retry_otp - Resend OTP if you're at the OTP verification stage
        """
        await event.reply(
            help_text,
            buttons=[
                [Button.inline("Start Forwarding", b'start_forwarding')],
                [Button.inline("Stop Forwarding", b'stop_forwarding')],
                [Button.inline("Check Status", b'status')]
            ]
        )

    @bot.on(events.NewMessage(pattern='/retry_otp'))
    async def retry_otp_command(event):
        try:
            await handle_retry_otp(event, event.sender_id)
        except Exception as e:
            logger.error(f"Error in retry_otp_command: {str(e)}")
            await event.reply(f"Error retrying OTP: {str(e)}")

    def is_valid_user_id(user_id):
        # Check if the user ID is a valid Telegram user ID (positive number)
        return user_id > 0

    logger.info("Commands set up successfully")
