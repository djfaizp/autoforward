# database.py
import os
from motor.motor_asyncio import AsyncIOMotorClient
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        try:
            mongodb_uri = os.getenv('MONGODB_URI')
            db_name = os.getenv('DB_NAME', 'Cluster0')
            if not mongodb_uri:
                raise ValueError("MONGODB_URI environment variable is not set")
            self.client = AsyncIOMotorClient(mongodb_uri)
            self.db = self.client[db_name]
            logger.info(f"Connected to MongoDB database: {db_name}")
            await self.ensure_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}", exc_info=True)
            raise

    async def disconnect(self):
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def ensure_indexes(self):
        indexes = await self.db.users.index_information()
        if 'user_id_1' not in indexes:
            await self.db.users.create_index('user_id', unique=True)

    async def save_user_credentials(self, user_id, credentials):
        try:
            user_id = int(user_id)
            if 'api_id' in credentials:
                credentials['api_id'] = int(credentials['api_id'])
            if 'source_channel' in credentials:
                credentials['source_channel'] = int(credentials['source_channel'])
            if 'destination_channel' in credentials:
                credentials['destination_channel'] = int(credentials['destination_channel'])

            users_collection = self.db.users
            await users_collection.update_one(
                {'user_id': user_id},
                {'$set': credentials},
                upsert=True
            )
            logger.info(f"Saved credentials for user {user_id}")
        except ValueError as e:
            logger.error(f"Invalid value in credentials for user {user_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to save user credentials: {str(e)}", exc_info=True)
            raise

    async def get_user_credentials(self, user_id):
        try:
            user_id = int(user_id)
            users_collection = self.db.users
            user_data = await users_collection.find_one({'user_id': user_id})
            if user_data:
                if 'api_id' in user_data:
                    user_data['api_id'] = int(user_data['api_id'])
                if 'source_channel' in user_data:
                    user_data['source_channel'] = int(user_data['source_channel'])
                if 'destination_channel' in user_data:
                    user_data['destination_channel'] = int(user_data['destination_channel'])
                return user_data
            else:
                logger.warning(f"No user data found for user ID {user_id}")
                return None
        except ValueError as e:
            logger.error(f"Invalid user_id: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get user credentials: {str(e)}", exc_info=True)
            raise

    async def mark_message_as_forwarded(self, user_id, message_id):
        try:
            forwarded_messages = self.db.forwarded_messages
            await forwarded_messages.update_one(
                {'user_id': user_id, 'message_id': message_id},
                {'$set': {'forwarded': True}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to mark message as forwarded: {str(e)}", exc_info=True)
            raise

    async def is_message_forwarded(self, user_id, message_id):
        try:
            forwarded_messages = self.db.forwarded_messages
            result = await forwarded_messages.find_one({'user_id': user_id, 'message_id': message_id, 'forwarded': True})
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check if message is forwarded: {str(e)}", exc_info=True)
            raise

    async def mark_filename_as_forwarded(self, user_id, filename):
        try:
            forwarded_filenames = self.db.forwarded_filenames
            await forwarded_filenames.update_one(
                {'user_id': user_id, 'filename': filename},
                {'$set': {'forwarded': True}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to mark filename as forwarded: {str(e)}", exc_info=True)
            raise

    async def is_filename_forwarded(self, user_id, filename):
        try:
            forwarded_filenames = self.db.forwarded_filenames
            result = await forwarded_filenames.find_one({'user_id': user_id, 'filename': filename, 'forwarded': True})
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check if filename is forwarded: {str(e)}", exc_info=True)
            raise

    async def update_forwarding_progress(self, user_id, messages_forwarded, current_id):
        try:
            users_collection = self.db.users
            updated_user = await users_collection.find_one_and_update(
                {'user_id': user_id},
                {'$set': {'messages_forwarded': int(messages_forwarded), 'current_id': int(current_id)}},
                return_document=True
            )
            return updated_user
        except Exception as e:
            logger.error(f"Failed to update forwarding progress: {str(e)}", exc_info=True)
            raise

    async def get_active_users(self):
        try:
            users_collection = self.db.users
            active_users = await users_collection.find({'forwarding': True}).to_list(length=None)
            return [user['user_id'] for user in active_users]
        except Exception as e:
            logger.error(f"Failed to get active users: {str(e)}", exc_info=True)
            raise

db = Database()
