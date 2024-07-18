# utils.py
import logging
from telethon import events
from auth import (
    start_auth,
    save_api_id,
    save_api_hash,
    save_phone_number,
    verify_otp,
    save_source_channel,
    save_destination_channel,
    AuthState,
    send_otp,
    handle_retry_otp
)
from database import db
from forwarder import Forwarder

logger = logging.getLogger(__name__)

def setup_commands(bot, user_client, forwarder: Forwarder):
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_command(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)
        if not user_data or not user_data.get('session_string'):
            await start_auth(event, user_id)
        else:
            await event.reply("Welcome back! You are already authenticated. Use /help to see available commands.")

    @bot.on(events.NewMessage(pattern=r'^(?!/start|/help|/start_forwarding|/stop_forwarding|/status)'))
    async def handle_auth(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)
        if user_data is None:
            logger.error(f"No user data found for user ID {user_id}")
            await event.reply("No user data found. Please start the authentication process again using /start.")
            return
        
        auth_state = user_data.get('auth_state')
        
        if auth_state == AuthState.REQUEST_API_ID:
            await save_api_id(event, user_id)
        elif auth_state == AuthState.REQUEST_API_HASH:
            await save_api_hash(event, user_id)
        elif auth_state == AuthState.REQUEST_PHONE_NUMBER:
            await save_phone_number(event, user_id)
        elif auth_state == AuthState.VERIFY_OTP:
            client = await send_otp(event, user_id)  # Get the client instance
            await verify_otp(event, user_id, client)
        elif auth_state == AuthState.REQUEST_SOURCE_CHANNEL:
            await save_source_channel(event, user_id)
        elif auth_state == AuthState.REQUEST_DESTINATION_CHANNEL:
            await save_destination_channel(event, user_id)

    @bot.on(events.NewMessage(pattern='/start_forwarding'))
    async def start_forwarding_command(event):
        await forwarder.start_forwarding(event, bot, db)

    @bot.on(events.NewMessage(pattern='/stop_forwarding'))
    async def stop_forwarding_command(event):
        await forwarder.stop_forwarding(event, db)

    @bot.on(events.NewMessage(pattern='/status'))
    async def status_command(event):
        await forwarder.status(event, db)

    @bot.on(events.NewMessage(pattern='/help'))
    async def help_command(event):
        help_text = """
        Available commands:
        /start - Start the bot and begin authentication
        /help - Show this help message
        /start_forwarding <start_id>-<end_id> - Start the forwarding process
        /stop_forwarding - Stop the forwarding process
        /status - Check the status of the forwarding process
        """
        await event.reply(help_text)

    @bot.on(events.CallbackQuery(data=b'retry_otp'))
    async def handle_retry_otp_command(event):
        await handle_retry_otp(event)

    logger.info("Commands set up successfully")
    
