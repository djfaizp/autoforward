# forwarder.py
import logging
import random
import asyncio
from telethon import types
from telethon.errors import FloodWaitError, MessageIdInvalidError, ChatWriteForbiddenError
from telethon.tl.types import MessageMediaWebPage, MessageService
from telethon.tl.functions.messages import ForwardMessagesRequest
from rate_limiter import UserRateLimiter
from utils import retry_with_backoff
from media_handler import MediaHandler
from message_queue import MessageQueue
from database import Database

logger = logging.getLogger(__name__)

class Forwarder:
    def __init__(self, user_client, db: Database, config, max_retries=3):
        self.user_client = user_client
        self.db = db
        self.rate_limiter = UserRateLimiter(config.MAX_FORWARD_BATCH, 60)
        self.max_retries = max_retries
        self.max_forward_batch = config.MAX_FORWARD_BATCH
        self.forward_delay_min = config.FORWARD_DELAY_MIN
        self.forward_delay_max = config.FORWARD_DELAY_MAX
        self.media_handler = MediaHandler(db)
        self.message_queue = MessageQueue(db)

    def generate_random_id(self):
        return random.getrandbits(64)

    async def validate_channel(self, channel_id):
        try:
            if isinstance(channel_id, str) and channel_id.startswith('-100'):
                channel_id = int(channel_id)
            entity = await self.user_client.client.get_entity(channel_id)
            return entity
        except ValueError:
            logger.error(f"Cannot find any entity corresponding to {channel_id}")
            raise

    async def validate_channel(self, channel_id):
        try:
            entity = await self.user_client.client.get_entity(channel_id)  # Removed int conversion
            return entity
        except ValueError:
            logger.error(f"Cannot find any entity corresponding to {channel_id}")
            raise

    async def forward_message(self, message, destination_channel):
        async def _forward():
            filename = None
            if message.media and not isinstance(message.media, MessageMediaWebPage):
                if hasattr(message.media, 'document'):
                    filename = message.media.document.attributes[0].file_name
                    file_metadata = await self.media_handler.extract_metadata(message.media.document)
                    if await self.media_handler.is_file_forwarded(file_metadata):
                        logger.warning(f"Duplicate filename detected: {filename}. Skipping.")
                        return None

                from_peer = await self.user_client.client.get_input_entity(message.peer_id)
<<<<<<< HEAD
                to_peer = await self.user_client.client.get_input_entity(destination_channel)

=======
                to_peer = await self.user_client.client.get_input_entity(destination_channel)  # Removed int conversion
                
>>>>>>> 495dcb0 (skip duplicate)
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
                    await self.media_handler.store_file_metadata(file_metadata)
            else:
<<<<<<< HEAD
                sent_message = await self.user_client.client.send_message(destination_channel, message.text or "")

            return sent_message

        return await retry_with_backoff(_forward)
=======
                sent_message = await self.user_client.client.send_message(destination_channel, message.text or "")  # Removed int conversion
            
            return sent_message
        except MessageTooLongError:
            truncated_text = (message.text or "")[:4096]
            logger.warning(f"Message too long, truncating: {truncated_text[:50]}...")
            return await self.user_client.client.send_message(destination_channel, truncated_text)  # Removed int conversion
        except ChatWriteForbiddenError:
            logger.error(f"Write permissions are not available in the destination channel: {destination_channel}")
            raise
        except Exception as e:
            logger.error(f"Error in forward_message: {str(e)}", exc_info=True)
            raise
>>>>>>> 495dcb0 (skip duplicate)

    async def forward_messages(self, user_id, bot, db, progress_message, start_id=None, end_id=None):
        logger.info(f"Starting forwarding process for user {user_id}")
        user_data = await db.get_user_credentials(user_id)

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
            source_channel = await self.validate_channel(user_data['source'])
            destination_channel = await self.validate_channel(user_data['destination'])
        except ValueError:
            await bot.edit_message(user_id, progress_message.id, "Error: Invalid source or destination channel.")
            await db.save_user_credentials(user_id, {'forwarding': False})
            return

        while user_data['forwarding'] and current_id <= end_id:
            try:
<<<<<<< HEAD
                message_ids = list(range(current_id, min(current_id + self.max_forward_batch, end_id + 1)))
                messages = await self.user_client.client.get_messages(source_channel, ids=message_ids)
=======
                messages = await self.user_client.client.get_messages(source_channel, ids=[current_id])
>>>>>>> 495dcb0 (skip duplicate)
                if not messages:
                    logger.warning(f"No messages found in range {current_id}-{current_id + self.max_forward_batch}.")
                    current_id += self.max_forward_batch
                    continue

<<<<<<< HEAD
                # Filter out duplicate filenames before processing
                unique_messages = []
                for message in messages:
                    if message.media and not isinstance(message.media, MessageMediaWebPage) and hasattr(message.media, 'document'):
                        filename = message.media.document.attributes[0].file_name
                        if await self.db.is_filename_forwarded(message.sender_id, filename):
                            logger.warning(f"Duplicate filename detected: {filename}. Skipping message ID {message.id}.")
                            skipped_messages.append((message.id, "Duplicate filename detected"))
                            continue
                    unique_messages.append(message)
=======
                if not isinstance(message, MessageService) and not await self.db.is_message_forwarded(user_id, message.id):
                    for retry in range(self.max_retries):
                        try:
                            await self.rate_limiter.wait()
                            sent_message = await self.forward_message(message, destination_channel)
                            if sent_message:
                                await self.db.mark_message_as_forwarded(user_id, message.id)
                                messages_forwarded += 1
                                logger.debug(f"Forwarded message {message.id} as new message {sent_message.id}")
                            else:
                                skipped_messages.append((message.id, "Duplicate filename detected"))
                            break
                        except FloodWaitError as fwe:
                            logger.warning(f"FloodWaitError: Waiting for {fwe.seconds} seconds")
                            await asyncio.sleep(fwe.seconds)
                        except MessageIdInvalidError:
                            logger.warning(f"Invalid message ID: {message.id}. Skipping.")
                            skipped_messages.append((message.id, "Invalid message ID"))
                            break
                        except ChatWriteForbiddenError:
                            logger.error(f"Write permissions are not available in the destination channel: {user_data['destination']}")
                            skipped_messages.append((message.id, "Write permissions are not available in the destination channel"))
                            break
                        except Exception as e:
                            logger.error(f"Error forwarding message {message.id}: {str(e)}", exc_info=True)
                            if retry == self.max_retries - 1:
                                logger.error(f"Max retries reached for message {message.id}. Skipping.")
                                skipped_messages.append((message.id, str(e)))
                    
                    await asyncio.sleep(random.randint(0, 1))
>>>>>>> 495dcb0 (skip duplicate)

                for message in unique_messages:
                    if not isinstance(message, MessageService) and not await self.db.is_message_forwarded(user_id, message.id):
                        for retry in range(self.max_retries):
                            try:
                                await self.rate_limiter.wait(user_id)
                                sent_message = await self.forward_message(message, destination_channel)
                                if sent_message:
                                    await self.db.mark_message_as_forwarded(user_id, message.id)
                                    messages_forwarded += 1
                                    messages_processed += 1  # Increment processed messages counter
                                    logger.debug(f"Forwarded message {message.id} as new message {sent_message.id}")
                                else:
                                    skipped_messages.append((message.id, "Duplicate filename detected"))
                                break
                            except FloodWaitError as fwe:
                                logger.warning(f"FloodWaitError: Waiting for {fwe.seconds} seconds")
                                await asyncio.sleep(fwe.seconds)
                            except MessageIdInvalidError:
                                logger.warning(f"Invalid message ID: {message.id}. Skipping.")
                                skipped_messages.append((message.id, "Invalid message ID"))
                                break
                            except ChatWriteForbiddenError:
                                logger.error(f"Write permissions are not available in the destination channel: {user_data['destination']}")
                                skipped_messages.append((message.id, "Write permissions are not available in the destination channel"))
                                break
                            except Exception as e:
                                logger.error(f"Error forwarding message {message.id}: {str(e)}", exc_info=True)
                                if retry == self.max_retries - 1:
                                    logger.error(f"Max retries reached for message {message.id}. Skipping.")
                                    skipped_messages.append((message.id, str(e)))

                        await asyncio.sleep(random.randint(0, 1))

                current_id += self.max_forward_batch

                # Implementing delay after every MAX_FORWARD_BATCH messages
                if messages_processed >= self.max_forward_batch:
                    delay = random.randint(self.forward_delay_min, self.forward_delay_max)
                    logger.info(f"Processed {self.max_forward_batch} messages, waiting for {delay} seconds...")
                    await asyncio.sleep(delay)  # Delay for a random time between FORWARD_DELAY_MIN and FORWARD_DELAY_MAX
                    messages_processed = 0  # Reset counter

                # Update progress in the database
                await db.update_forwarding_progress(user_id, messages_forwarded, current_id)

                progress_percentage = (messages_forwarded / total_messages) * 100
                progress_content = f"Forwarding progress: {progress_percentage:.2f}% ({messages_forwarded}/{total_messages})"

                if progress_content != last_progress_content:
                    await bot.edit_message(user_id, progress_message.id, progress_content)
                    last_progress_content = progress_content

                # Fetch the latest user data to check if forwarding has been stopped
                user_data = await db.get_user_credentials(user_id)
                if not user_data['forwarding']:
                    logger.info(f"User {user_id} stopped forwarding process")
                    break

            except Exception as e:
                logger.error(f"Error during forwarding for user {user_id}: {str(e)}", exc_info=True)
                await bot.edit_message(user_id, progress_message.id, f"An error occurred during forwarding: {str(e)}")
                break

        await db.update_forwarding_progress(user_id, messages_forwarded, current_id)
        await db.save_user_credentials(user_id, {'forwarding': False})
        logger.info(f"Forwarding process completed for user {user_id}")
        completion_message = f"Forwarding process completed. Total messages forwarded: {messages_forwarded}"
        if skipped_messages:
            skipped_info = "\n".join([f"Message ID {msg_id}: {reason}" for msg_id, reason in skipped_messages])
            completion_message += f"\nSkipped messages:\n{skipped_info}"
        await bot.edit_message(user_id, progress_message.id, completion_message)
