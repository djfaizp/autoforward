# commands.py
import asyncio
import json
import logging
from telethon import events
<<<<<<< HEAD
=======
from telethon.errors import ChannelPrivateError, UserNotParticipantError
>>>>>>> 495dcb0 (skip duplicate)
from typing import Any

logger = logging.getLogger(__name__)

def setup_commands(bot: Any, user_client: Any, forwarder: Any, db: Any):
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_command(event):
        user_id = event.sender_id
        logger.info(f"User {user_id} started the bot")
        await event.reply("Welcome to the Autoforward bot! Use /help to see available commands.")

    @bot.on(events.NewMessage(pattern='/help'))
    async def help_command(event):
        user_id = event.sender_id
        logger.info(f"User {user_id} requested help")
        help_text = """
        Available commands:
        /start - Start the bot
        /help - Show this help message
        /set_api_id <api_id> - Set the API ID for user client
        /set_api_hash <api_hash> - Set the API Hash for user client
        /set_session_string <session_string> - Set the session string for user client (optional)
        /set_source <channel_id> - Set the source channel
        /set_destination <channel_id> - Set the destination channel
        /start_forwarding <start_id>-<end_id> - Start the forwarding process with message ID range
        /resume_forwarding - Resume the forwarding process from the last saved state
        /status - Check the status of the forwarding process
        /stop_forwarding - Stop the forwarding process
        """
        await event.reply(help_text)

    @bot.on(events.NewMessage(pattern='/set_api_id'))
    async def set_api_id_command(event):
        user_id = event.sender_id
        try:
            _, api_id = event.text.split()
            api_id = int(api_id)
            user_data = await db.get_user_credentials(user_id)
            user_data['api_id'] = api_id
            await db.save_user_credentials(user_id, user_data)
            logger.info(f"User {user_id} set API ID")
            await event.reply("API ID set successfully")
        except ValueError:
            logger.warning(f"User {user_id} provided invalid format for set_api_id")
            await event.reply("Invalid API ID. Please provide a valid integer.")
        except Exception as e:
            logger.error(f"Unexpected error in set_api_id_command: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")

    @bot.on(events.NewMessage(pattern='/set_api_hash'))
    async def set_api_hash_command(event):
        user_id = event.sender_id
        try:
            _, api_hash = event.text.split()
            if len(api_hash) != 32:
                raise ValueError("API Hash should be 32 characters long")
            user_data = await db.get_user_credentials(user_id)
            user_data['api_hash'] = api_hash
            await db.save_user_credentials(user_id, user_data)
            logger.info(f"User {user_id} set API Hash")
            await event.reply("API Hash set successfully")
        except ValueError as e:
            logger.warning(f"User {user_id} provided invalid format for set_api_hash: {str(e)}")
            await event.reply(f"Invalid API Hash. {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in set_api_hash_command: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")
            
    @bot.on(events.NewMessage(pattern='/set_session_string'))
    async def set_session_string_command(event):
        user_id = event.sender_id
        logger.debug(f"Received /set_session_string command from user {user_id}")
        try:
            _, session_string = event.text.split(maxsplit=1)
            user_data = await db.get_user_credentials(user_id)
            user_data['session_string'] = session_string
            await db.save_user_credentials(user_id, user_data)
            logger.info(f"User {user_id} set session string: {session_string}")
            await event.reply("Session string set successfully")
        except ValueError:
            logger.warning(f"User {user_id} provided invalid format for /set_session_string")
            await event.reply("Invalid session string format. Please use: /set_session_string <session_string>")
        except Exception as e:
            logger.error(f"Unexpected error in /set_session_string command: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")

    @bot.on(events.NewMessage(pattern='/set_source'))
    async def set_source_command(event):
        user_id = event.sender_id
        logger.debug(f"Received /set_source command from user {user_id}")
        try:
            _, source_channel = event.text.split()
<<<<<<< HEAD
            source_channel = int(source_channel)
            user_data = await db.get_user_credentials(user_id)
            user_data['source'] = source_channel
            await db.save_user_credentials(user_id, user_data)
=======
            source_channel = int(source_channel)  # Ensure the channel ID is stored as an integer
            await db.save_user_credentials(user_id, {'source': source_channel})
>>>>>>> 495dcb0 (skip duplicate)
            logger.info(f"User {user_id} set source channel: {source_channel}")
            await event.reply("Source channel set successfully")
        except ValueError:
            logger.warning(f"User {user_id} provided invalid format for /set_source")
            await event.reply("Invalid source channel format. Please use: /set_source <channel_id>")
        except Exception as e:
            logger.error(f"Unexpected error in /set_source command: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")

    @bot.on(events.NewMessage(pattern='/set_destination'))
    async def set_destination_command(event):
        user_id = event.sender_id
        logger.debug(f"Received /set_destination command from user {user_id}")
        try:
            _, destination_channel = event.text.split()
<<<<<<< HEAD
            destination_channel = int(destination_channel)
            user_data = await db.get_user_credentials(user_id)
            user_data['destination'] = destination_channel
            await db.save_user_credentials(user_id, user_data)
=======
            destination_channel = int(destination_channel)  # Ensure the channel ID is stored as an integer
            await db.save_user_credentials(user_id, {'destination': destination_channel})
>>>>>>> 495dcb0 (skip duplicate)
            logger.info(f"User {user_id} set destination channel: {destination_channel}")
            await event.reply("Destination channel set successfully")
        except ValueError:
            logger.warning(f"User {user_id} provided invalid format for /set_destination")
            await event.reply("Invalid destination channel format. Please use: /set_destination <channel_id>")
        except Exception as e:
            logger.error(f"Unexpected error in /set_destination command: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")

    @bot.on(events.NewMessage(pattern='/status'))
    async def status_command(event):
        user_id = event.sender_id
        user_data = await db.get_user_credentials(user_id)
        if user_data and user_data.get('forwarding'):
            messages_forwarded = user_data.get('messages_forwarded', 0)
            start_id = user_data.get('start_id')
            end_id = user_data.get('end_id')
            progress_percentage = (messages_forwarded / (end_id - start_id + 1)) * 100
            await event.reply(f"Forwarding progress: {progress_percentage:.2f}% ({messages_forwarded}/{end_id - start_id + 1})")
        else:
            await event.reply("No forwarding process in progress.")

    @bot.on(events.NewMessage(pattern='/stop_forwarding'))
    async def stop_forwarding_command(event):
        user_id = event.sender_id
        try:
            user_data = await db.get_user_credentials(user_id)
            user_data['forwarding'] = False
            await db.save_user_credentials(user_id, user_data)
            logger.info(f"User {user_id} stopped forwarding process")
            await event.reply("Forwarding process stopped.")
        except Exception as e:
            logger.error(f"Unexpected error in stop_forwarding_command: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")

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
        user_data.update({
            'forwarding': True,
            'messages_forwarded': 0,
            'start_id': start_id,
            'end_id': end_id,
            'current_id': start_id
        })
        await db.save_user_credentials(user_id, user_data)

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
        user_data['forwarding'] = True
        await db.save_user_credentials(user_id, user_data)

        logger.info(f"User {user_id} resumed forwarding process from message ID {start_id} to {end_id}")
        progress_message = await event.reply(f"Resumed forwarding process from message ID {start_id} to {end_id}. Use /status to check the progress.")

        # Resume the forwarding process in a new asyncio task
        asyncio.create_task(forwarder.forward_messages(user_id, bot, db, progress_message, start_id=start_id, end_id=end_id))
