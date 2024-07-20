# file: utils.py
import logging
import asyncio
from telethon import events, Button
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
            await event.reply(
                "Welcome back! You are already authenticated. Use /help to see available commands.",
                buttons=[
                    [Button.inline("Help", b'help')]
                ]
            )

    @bot.on(events.NewMessage(pattern=r'^(?!/start|/help|/start_forwarding|/stop_forwarding|/status|/resume_forwarding)'))
    async def handle_auth(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)
        if user_data is None:
            logger.info(f"No user data found for user ID {user_id}. Skipping auth process.")
            return  # Skip processing if no user data is found

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
        /start_forwarding <start_id>-<end_id> - Start the forwarding process
        /stop_forwarding - Stop the forwarding process
        /status - Check the status of the forwarding process
        /resume_forwarding - Resume the forwarding process from the last stopped point
        """
        await event.reply(
            help_text,
            buttons=[
                [Button.inline("Start Forwarding", b'start_forwarding')],
                [Button.inline("Stop Forwarding", b'stop_forwarding')],
                [Button.inline("Check Status", b'status')],
                [Button.inline("Resume Forwarding", b'resume_forwarding')]
            ]
        )

    @bot.on(events.NewMessage(pattern='/resume_forwarding'))
    async def resume_forwarding_command(event):
        user_id = event.sender_id

        user_data = await db.get_user_credentials(user_id)
        if not user_data:
            logger.warning(f"User {user_id} attempted to resume forwarding without any credentials")
            await event.reply("Please set up your credentials first. Use /help to see the available commands.")
            return

        missing_credentials = []
        for cred in ['api_id', 'api_hash', 'source', 'destination']:
            if cred not in user_data:
                missing_credentials.append(cred.replace('_', ' ').title())

        if missing_credentials:
            missing_cred_str = ", ".join(missing_credentials)
            logger.warning(f"User {user_id} attempted to resume forwarding with missing credentials: {missing_cred_str}")
            await event.reply(f"Please set up the following before resuming: {missing_cred_str}. Use /help for instructions.")
            return

        if not user_client.client:
            try:
                await user_client.start(user_data['api_id'], user_data['api_hash'], user_data.get('session_string'))
            except Exception as e:
                logger.error(f"Failed to start user client for user {user_id}: {str(e)}", exc_info=True)
                await event.reply("Failed to start user client. Please check your API ID and API Hash.")
                return

        if user_data.get('forwarding'):
            logger.info(f"User {user_id} attempted to resume forwarding while it's already in progress")
            await event.reply("Forwarding is already in progress. Use /status to check the progress.")
            return

        start_id = user_data.get('current_id')
        end_id = user_data.get('end_id')
        await db.save_user_credentials(user_id, {'forwarding': True})

        logger.info(f"User {user_id} resumed forwarding process from message ID {start_id} to {end_id}")
        progress_message = await event.reply(f"Resumed forwarding process from message ID {start_id} to {end_id}. Use /status to check the progress.")

        asyncio.create_task(forwarder.forward_messages(user_id, bot, db, progress_message, start_id=start_id, end_id=end_id))

    @bot.on(events.CallbackQuery(data=b'retry_otp'))
    async def handle_retry_otp_command(event):
        try:
            await handle_retry_otp(event)
        except Exception as e:
            logger.error(f"Error in handle_retry_otp_command: {str(e)}")
            await event.reply(f"Error retrying OTP: {str(e)}")

    logger.info("Commands set up successfully")
