# forwarder.py

import asyncio
import logging
import random
from telethon import types
from telethon.helpers import generate_random_long
from telethon.errors import FloodWaitError, MessageIdInvalidError, MessageTooLongError, ChatWriteForbiddenError
from telethon.tl.types import MessageMediaWebPage, MessageService
from telethon.tl.functions.messages import ForwardMessagesRequest
from rate_limiter import UserRateLimiter
from cachetools import TTLCache
from collections import deque

logger = logging.getLogger(__name__)

class Forwarder:
    def __init__(self, user_client, db, config, max_retries=3):
        self.user_client = user_client
        self.db = db
        self.rate_limiter = UserRateLimiter(config.MAX_FORWARD_BATCH, 60)
        self.max_retries = max_retries
        self.max_forward_batch = config.MAX_FORWARD_BATCH
        self.forward_delay_min = config.FORWARD_DELAY_MIN
        self.forward_delay_max = config.FORWARD_DELAY_MAX
        self.forwarding_tasks = {}
        self.forwarded_cache = set()  # In-memory cache for forwarded messages
        self.user_cache = TTLCache(maxsize=100, ttl=300)  # Caching user credentials
        self.queue = deque()  # Task queue

    async def forward_messages(self, user_id, bot, db, progress_message, start_id=None, end_id=None):
        user_data = await self.get_user_credentials(user_id)
        await self.ensure_user_client_started(user_data)

        if start_id is not None and end_id is not None:
            user_data.update({
                'start_id': int(start_id),
                'end_id': int(end_id),
                'current_id': int(start_id),
                'messages_forwarded': 0,
                'forwarding': True
            })
            await self.save_user_credentials(user_id, user_data)

        total_messages = user_data['end_id'] - user_data['start_id'] + 1
        current_id = user_data['current_id']
        messages_forwarded = user_data['messages_forwarded']

        try:
            source_channel = await self.validate_channel(user_data['source'])
            destination_channel = await self.validate_channel(user_data['destination'])
        except ValueError:
            await bot.edit_message(user_id, progress_message.id, "Error: Invalid source or destination channel.")
            await self.save_user_credentials(user_id, {'forwarding': False})
            return

        while user_data['forwarding'] and current_id <= user_data['end_id']:
            batch_message_ids = list(range(current_id, min(current_id + self.max_forward_batch, user_data['end_id'] + 1)))
            batch_messages = await self.user_client.client.get_messages(source_channel, ids=batch_message_ids)

            forwarded_batch = await asyncio.gather(*[
                self.process_message(message, user_id, destination_channel)
                for message in batch_messages if message and not isinstance(message, MessageService)
            ])

            messages_forwarded += sum(1 for msg in forwarded_batch if msg)
            current_id += self.max_forward_batch

            await self.update_progress(user_id, bot, progress_message, messages_forwarded, total_messages)

            await asyncio.sleep(random.randint(self.forward_delay_min, self.forward_delay_max))

            user_data = await self.get_user_credentials(user_id)
            if not user_data['forwarding']:
                break

        await self.update_progress(user_id, bot, progress_message, messages_forwarded, total_messages, final=True)
        await self.save_user_credentials(user_id, {'forwarding': False, 'messages_forwarded': messages_forwarded, 'current_id': current_id})

    async def process_message(self, message, user_id, destination_channel):
        if message.id in self.forwarded_cache or await self.db.is_message_forwarded(user_id, message.id):
            return None

        for retry in range(self.max_retries):
            try:
                await self.rate_limiter.wait(user_id)
                sent_message = await self.forward_message(message, destination_channel)
                if sent_message:
                    self.forwarded_cache.add(message.id)
                    await self.db.mark_message_as_forwarded(user_id, message.id)
                    return sent_message
            except FloodWaitError as fwe:
                await asyncio.sleep(fwe.seconds)
            except (MessageIdInvalidError, ChatWriteForbiddenError):
                return None
            except Exception as e:
                logger.error(f"Error forwarding message {message.id}: {str(e)}", exc_info=True)
                if retry == self.max_retries - 1:
                    return None
        return None

    async def forward_message(self, message, destination_channel):
        if message.media and not isinstance(message.media, MessageMediaWebPage):
            from_peer = await self.user_client.client.get_input_entity(message.peer_id)
            to_peer = await self.user_client.client.get_input_entity(destination_channel)
            
            result = await self.user_client.client(ForwardMessagesRequest(
                from_peer=from_peer,
                id=[message.id],
                to_peer=to_peer,
                random_id=[generate_random_long()],
                drop_author=True
            ))
            
            for update in result.updates:
                if isinstance(update, types.UpdateNewChannelMessage):
                    return update.message
            
            raise AttributeError(f"No 'UpdateNewChannelMessage' found in updates. Result: {result.to_dict()}")
        else:
            return await self.user_client.client.send_message(destination_channel, message.text or "")

    async def update_progress(self, user_id, bot, progress_message, messages_forwarded, total_messages, final=False):
        progress_percentage = (messages_forwarded / total_messages) * 100
        progress_content = f"Forwarding progress: {progress_percentage:.2f}% ({messages_forwarded}/{total_messages})"
        if final:
            progress_content += "\nForwarding process completed."
        
        # Update the progress message
        await bot.edit_message(user_id, progress_message.id, progress_content)
        
        # Save the updated progress to the database
        await self.db.update_forwarding_progress(user_id, messages_forwarded, current_id)

    async def ensure_user_client_started(self, user_data):
        if not self.user_client.client or not self.user_client.client.is_connected():
            await self.user_client.start(user_data['api_id'], user_data['api_hash'], user_data.get('session_string'))
            logger.info("User client started successfully in ensure_user_client_started")

    async def validate_channel(self, channel_id):
        try:
            if not self.user_client.client or not self.user_client.client.is_connected():
                logger.error("User client is not connected")
                raise ValueError("User client is not connected")
            
            if isinstance(channel_id, str) and channel_id.startswith('-100'):
                channel_id = int(channel_id)
            entity = await self.user_client.client.get_entity(channel_id)
            return entity
        except ValueError:
            logger.error(f"Cannot find any entity corresponding to {channel_id}")
            raise

    async def get_user_credentials(self, user_id):
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        user_data = await self.db.get_user_credentials(user_id)
        self.user_cache[user_id] = user_data
        return user_data

    async def save_user_credentials(self, user_id, user_data):
        self.user_cache[user_id] = user_data
        await self.db.save_user_credentials(user_id, user_data)

    async def worker(self):
        while True:
            if self.queue:
                user_id, bot, db, progress_message, start_id, end_id = self.queue.popleft()
                await self.forward_messages(user_id, bot, db, progress_message, start_id, end_id)
            await asyncio.sleep(1)

    async def start_forwarding(self, event, bot, db):
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

        user_data = await self.get_user_credentials(user_id)
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

        if not self.user_client.client:
            try:
                await self.user_client.start(user_data['api_id'], user_data['api_hash'], user_data.get('session_string'))
            except Exception as e:
                logger.error(f"Failed to start user client for user {user_id}: {str(e)}", exc_info=True)
                await event.reply("Failed to start user client. Please check your API ID and API Hash.")
                return

        # Reset forwarding state
        await self.save_user_credentials(user_id, {
            'forwarding': True,
            'messages_forwarded': 0,
            'start_id': start_id,
            'end_id': end_id,
            'current_id': start_id
        })

        logger.info(f"User {user_id} started forwarding process from message ID {start_id} to {end_id}")
        progress_message = await event.reply(f"Forwarding process started from message ID {start_id} to {end_id}. Use /status to check the progress.")

        # Add the task to the queue
        self.queue.append((user_id, bot, db, progress_message, start_id, end_id))
        logger.info(f"User {user_id} added to the forwarding queue with range {start_id}-{end_id}")

    async def stop_forwarding(self, event, db):
        user_id = event.sender_id
        try:
            await self.save_user_credentials(user_id, {'forwarding': False})
            logger.info(f"User {user_id} requested to stop forwarding process")
            await event.reply("Stopping the forwarding process. Please wait...")
            
            await self.interrupt_forwarding(user_id)
            
            await event.reply("Forwarding process has been stopped.")
        except Exception as e:
            logger.error(f"Unexpected error in stop_forwarding: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")

    async def status(self, event, db):
        user_id = event.sender_id
        user_data = await self.get_user_credentials(user_id)
        if user_data and user_data.get('forwarding'):
            messages_forwarded = user_data.get('messages_forwarded', 0)
            start_id = user_data.get('start_id')
            end_id = user_data.get('end_id')
            progress_percentage = (messages_forwarded / (end_id - start_id + 1)) * 100
            await event.reply(f"Forwarding progress: {progress_percentage:.2f}% ({messages_forwarded}/{end_id - start_id + 1})")
        else:
            await event.reply("No forwarding process in progress.")

    async def interrupt_forwarding(self, user_id):
        if user_id in self.forwarding_tasks:
            task = self.forwarding_tasks[user_id]
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Cancellation of forwarding task for user {user_id} timed out")
            except asyncio.CancelledError:
                pass
            logger.info(f"Forwarding task for user {user_id} has been cancelled.")
        else:
            logger.warning(f"No active forwarding task found for user {user_id}")

    async def process_user_queue(self, user_id, bot, db, progress_message):
        logger.info(f"Processing queue for user {user_id}")
        task = asyncio.create_task(self.forward_messages(user_id, bot, db, progress_message))
        self.forwarding_tasks[user_id] = task
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Forwarding task for user {user_id} was cancelled.")
        finally:
            if user_id in self.forwarding_tasks:
                del self.forwarding_tasks[user_id]
        logger.info(f"Completed processing queue for user {user_id}")
            
