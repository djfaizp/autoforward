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
        self.forwarding_tasks = {}  # Dictionary to keep track of forwarding tasks

    def generate_random_id(self):
        return generate_random_long()

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

    async def ensure_user_client_started(self, user_data):
        if not self.user_client.client or not self.user_client.client.is_connected():
            await self.user_client.start(user_data['api_id'], user_data['api_hash'], user_data.get('session_string'))
            logger.info("User client started successfully in ensure_user_client_started")

    async def forward_message(self, message, destination_channel):
        try:
            filename = None
            if message.media and not isinstance(message.media, MessageMediaWebPage):
                if hasattr(message.media, 'document'):
                    filename = message.media.document.attributes[0].file_name
                    if await self.db.is_filename_forwarded(message.sender_id, filename):
                        logger.warning(f"Duplicate filename detected: {filename}. Skipping.")
                        return None
                
                from_peer = await self.user_client.client.get_input_entity(message.peer_id)
                to_peer = await self.user_client.client.get_input_entity(destination_channel)
                
                result = await self.user_client.client(ForwardMessagesRequest(
                    from_peer=from_peer,
                    id=[message.id],
                    to_peer=to_peer,
                    random_id=[self.generate_random_id()],
                    drop_author=True
                ))
                
                sent_message = None
                for update in result.updates:
                    if isinstance(update, types.UpdateNewChannelMessage):
                        sent_message = update.message
                        break
                
                if not sent_message:
                    logger.error(f"No 'UpdateNewChannelMessage' found in updates. Result: {result.to_dict()}")
                    raise AttributeError(f"No 'UpdateNewChannelMessage' found in updates. Result: {result.to_dict()}")
                
                if filename:
                    await self.db.mark_filename_as_forwarded(message.sender_id, filename)
            else:
                sent_message = await self.user_client.client.send_message(destination_channel, message.text or "")
            
            return sent_message
        except MessageTooLongError:
            truncated_text = (message.text or "")[:4096]
            logger.warning(f"Message too long, truncating: {truncated_text[:50]}...")
            return await self.user_client.client.send_message(destination_channel, truncated_text)
        except ChatWriteForbiddenError:
            logger.error(f"Write permissions are not available in the destination channel: {destination_channel}")
            raise
        except Exception as e:
            logger.error(f"Error in forward_message: {str(e)}", exc_info=True)
            raise

    async def forward_messages(self, user_id, bot, db, progress_message, start_id=None, end_id=None):
        logger.info(f"Starting forwarding process for user {user_id}")
        user_data = await db.get_user_credentials(user_id)

        await self.ensure_user_client_started(user_data)

        if start_id is not None and end_id is not None:
            await db.save_user_credentials(user_id, {
                'start_id': int(start_id),
                'end_id': int(end_id),
                'current_id': int(start_id),
                'messages_forwarded': 0,
                'forwarding': True
            })
            user_data = await db.get_user_credentials(user_id)
        else:
            start_id = user_data['current_id']
            end_id = user_data['end_id']

        total_messages = end_id - start_id + 1
        current_id = user_data['current_id']
        messages_forwarded = user_data['messages_forwarded']
        skipped_messages = []
        last_progress_content = ""
        messages_processed = 0  # Counter for processed messages

        try:
            source_channel = await self.validate_channel(user_data['source'])
            destination_channel = await self.validate_channel(user_data['destination'])
        except ValueError:
            await bot.edit_message(user_id, progress_message.id, "Error: Invalid source or destination channel.")
            await db.save_user_credentials(user_id, {'forwarding': False})
            return

        try:
            while user_data['forwarding'] and current_id <= end_id:
                # Check if forwarding should be stopped
                user_data = await db.get_user_credentials(user_id)
                if not user_data['forwarding']:
                    logger.info(f"Stopping forwarding for user {user_id} as requested.")
                    break

                logger.debug(f"Fetching messages from {current_id} to {min(current_id + self.max_forward_batch, end_id + 1)}")
                batch_message_ids = list(range(current_id, min(current_id + self.max_forward_batch, end_id + 1)))
                batch_messages = await self.user_client.client.get_messages(source_channel, ids=batch_message_ids)
                if not batch_messages:
                    logger.warning(f"No messages found in the range {current_id} to {min(current_id + self.max_forward_batch, end_id + 1)}")
                    break

                for message in batch_messages:
                    if message is None:
                        logger.warning(f"Received None message in batch for message ID {current_id}")
                        current_id += 1
                        continue
                    
                    logger.debug(f"Processing message ID {message.id}")
                    if message and not isinstance(message, MessageService) and not await self.db.is_message_forwarded(user_id, message.id):
                        logger.debug(f"Message ID {message.id} is not forwarded yet and is not a service message")
                        for retry in range(self.max_retries):
                            try:
                                await self.rate_limiter.wait(user_id)
                                sent_message = await self.forward_message(message, destination_channel)
                                if sent_message:
                                    await self.db.mark_message_as_forwarded(user_id, message.id)
                                    messages_forwarded += 1
                                    messages_processed += 1
                                    logger.info(f"Message ID {message.id} forwarded successfully as new message ID {sent_message.id}")
                                break
                            except FloodWaitError as fwe:
                                logger.warning(f"FloodWaitError: Waiting for {fwe.seconds} seconds")
                                await asyncio.sleep(fwe.seconds)
                            except MessageIdInvalidError:
                                logger.warning(f"Invalid message ID: {message.id}. Skipping.")
                                break
                            except ChatWriteForbiddenError:
                                logger.error(f"Write permissions are not available in the destination channel: {user_data['destination']}")
                                return
                            except Exception as e:
                                logger.error(f"Error forwarding message {message.id}: {str(e)}", exc_info=True)
                                if retry == self.max_retries - 1:
                                    break
                        await asyncio.sleep(random.randint(0, 1))

                current_id += self.max_forward_batch

                if messages_processed >= self.max_forward_batch:
                    delay = random.randint(self.forward_delay_min, self.forward_delay_max)
                    logger.info(f"Processed {self.max_forward_batch} messages, waiting for {delay} seconds...")
                    await asyncio.sleep(delay)
                    messages_processed = 0

                await db.update_forwarding_progress(user_id, messages_forwarded, current_id)
                progress_percentage = (messages_forwarded / total_messages) * 100
                progress_content = f"Forwarding progress: {progress_percentage:.2f}% ({messages_forwarded}/{total_messages})"

                if progress_content != last_progress_content:
                    await bot.edit_message(user_id, progress_message.id, progress_content)
                    last_progress_content = progress_content

                user_data = await db.get_user_credentials(user_id)
                if not user_data['forwarding']:
                    logger.info(f"User {user_id} requested to stop forwarding.")
                    break

                # Check for task cancellation
                if asyncio.current_task().cancelled():
                    logger.info(f"Forwarding task for user {user_id} was cancelled.")
                    break

            logger.info(f"Forwarding process completed for user {user_id}")
        except asyncio.CancelledError:
            logger.info(f"Forwarding task for user {user_id} was cancelled.")
        finally:
            await db.save_user_credentials(user_id, {'forwarding': False})
            if user_id in self.forwarding_tasks:
                del self.forwarding_tasks[user_id]

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

        if not self.user_client.client:
            try:
                await self.user_client.start(user_data['api_id'], user_data['api_hash'], user_data.get('session_string'))
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
        asyncio.create_task(self.forward_messages(user_id, bot, db, progress_message))

    async def stop_forwarding(self, event, db):
        user_id = event.sender_id
        try:
            await db.save_user_credentials(user_id, {'forwarding': False})
            logger.info(f"User {user_id} requested to stop forwarding process")
            await event.reply("Stopping the forwarding process. Please wait...")
            
            await self.interrupt_forwarding(user_id)
            
            await event.reply("Forwarding process has been stopped.")
        except Exception as e:
            logger.error(f"Unexpected error in stop_forwarding: {str(e)}", exc_info=True)
            await event.reply("An unexpected error occurred. Please try again later.")

    async def status(self, event, db):
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
