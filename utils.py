# utils.py
import logging
from telethon import TelegramClient, events
from auth import start_auth, save_api_id, save_api_hash, save_phone_number, verify_otp, save_source_channel, save_destination_channel, AuthState
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

    # Registering handlers for authentication steps
    @bot.on(events.NewMessage())
    async def handle_auth(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)
        auth_state = user_data.get('auth_state')
        if auth_state == AuthState.REQUEST_API_ID:
            await save_api_id(event, user_id)
        elif auth_state == AuthState.REQUEST_API_HASH:
            await save_api_hash(event, user_id)
        elif auth_state == AuthState.REQUEST_PHONE_NUMBER:
            await save_phone_number(event, user_id)
        elif auth_state == AuthState.VERIFY_OTP:
            await verify_otp(event, user_id)
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

    logger.info("Commands set up successfully")

async def generate_session_string(api_id, api_hash, phone_number, code):
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    await client.sign_in(phone_number, code)
    session_string = client.session.save()
    await client.disconnect()
    return session_string
