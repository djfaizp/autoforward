# forwarder.py

import logging
import random
import asyncio
from telethon import types
from telethon.helpers import generate_random_long
from telethon.errors import FloodWaitError, MessageIdInvalidError, MessageTooLongError, ChatWriteForbiddenError
from telethon.tl.types import MessageMediaWebPage, MessageService
from telethon.tl.functions.messages import ForwardMessagesRequest
from rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class Forwarder:
    def __init__(self, user_client, db, max_calls=20, period=60, max_retries=3):
        self.user_client = user_client
        self.db = db
        self.rate_limiter = RateLimiter(max_calls, period)
        self.max_retries = max_retries

    def generate_random_id(self):
        return generate_random_long()

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

        if start_id is not None and end_id is not None:
            await db.save_user_credentials(user_id, {
                'start_id': start_id,
                'end_id': end_id,
                'current_id': start_id,
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

        while user_data['forwarding'] and current_id <= end_id:
            try:
                messages = await self.user_client.client.get_messages(user_data['source'], ids=[current_id])
                if not messages:
                    logger.warning(f"Message ID {current_id} not found in source channel.")
                    current_id += 1
                    continue
                
                message = messages[0]

                if not isinstance(message, MessageService) and not await self.db.is_message_forwarded(user_id, message.id):
                    for retry in range(self.max_retries):
                        try:
                            await self.rate_limiter.wait()
                            sent_message = await self.forward_message(message, user_data['destination'])
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

                current_id += 1

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
