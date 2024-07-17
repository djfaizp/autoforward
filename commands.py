# commands.py
import logging
from telethon import events
from auth import initiate_user_interaction, handle_user_response, auth_state
from database import db  # Ensure the database module is imported
import asyncio

logger = logging.getLogger(__name__)

def setup_commands(bot, db):
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_command(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)
        if user_data and 'session_string' in user_data:
            await event.reply("Welcome back! Use /help to see available commands.")
        else:
            await initiate_user_interaction(event, user_id)

    @bot.on(events.NewMessage)
    async def handle_event(event):
        user_id = event.sender_id
        if user_id in auth_state:
            await handle_user_response(event, user_id)

    @bot.on(events.NewMessage(pattern='/help'))
    async def help_command(event):
        user_id = event.sender_id
        logger.info(f"User {user_id} requested help")
        help_text = """
        Available commands:
        /start - Start the bot
        /help - Show this help message
        /start_forwarding <start_id>-<end_id> - Start the forwarding process with message ID range
        /resume_forwarding - Resume the forwarding process from the last saved state
        /status - Check the status of the forwarding process
        /stop_forwarding - Stop the forwarding process
        """
        await event.reply(help_text)

    @bot.on(events.NewMessage(pattern='/start_forwarding'))
    async def start_forwarding_command(event):
        user_id = event.sender_id
        try:
            _, range_ids = event.text.split()
            start_id, end_id = map(int, range_ids.split('-'))
            if start_id >= end_id:
                raise ValueError("Start ID must be less than End ID")
        except ValueError as e:
            logger.warning(f"User {user_id} provided invalid format for start_forwarding: {str(e)}")
            await event.reply(f"Invalid command format. Use: /start_forwarding <start_id>-<end_id>. {str(e)}")
            return

        user_data = await db.get_user_credentials(user_id)
        if not user_data:
            logger.warning(f"User {user_id} attempted to start forwarding without any credentials")
            await event.reply("Please set up your credentials first. Use /help to see the available commands.")
            return

        missing_credentials = []
        for cred in ['api_id', 'api_hash', 'source', 'destination']:
            if cred not in user_data:
                missing_credentials.append(cred.replace('_', ' ').title())

        if missing_credentials:
            missing_cred_str = ", ".join(missing_credentials)
            logger.warning(f"User {user_id} attempted to start forwarding with missing credentials: {missing_cred_str}")
            await event.reply(f"Please set up the following before starting: {missing_cred_str}. Use /help for instructions.")
            return

        if not user_client.client:
            try:
                await user_client.start(user_data['api_id'], user_data['api_hash'], user_data.get('session_string'))
            except Exception as e:
                logger.error(f"Failed to start user client for user {user_id}: {str(e)}", exc_info=True)
                await event.reply("Failed to start user client. Please check your API ID and API Hash.")
                return

        # Reset forwarding state
        await db.save_user_credentials(user_id, {
            'forwarding': True,
            'messages_forwarded': 0,
            'start_id': start_id,
            'end_id': end_id,
            'current_id': start_id
        })

        logger.info(f"User {user_id} started forwarding process from message ID {start_id} to {end_id}")
        progress_message = await event.reply(f"Forwarding process started from message ID {start_id} to {end_id}. Use /status to check the progress.")

        # Start the forwarding process in a new asyncio task
        asyncio.create_task(forwarder.forward_messages(user_id, bot, db, progress_message))

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

        start_id = user_data['current_id']
        end_id = user_data['end_id']
        await db.save_user_credentials(user_id, {'forwarding': True})

        logger.info(f"User {user_id} resumed forwarding process from message ID {start_id} to {end_id}")
        progress_message = await event.reply(f"Resumed forwarding process from message ID {start_id} to {end_id}. Use /status to check the progress.")

        # Resume the forwarding process in a new asyncio task
        asyncio.create_task(forwarder.forward_messages(user_id, bot, db, progress_message, start_id=start_id, end_id=end_id))

    logger.info("Commands set up successfully")
