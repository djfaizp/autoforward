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
        indexes = await self.db.forwarded_messages.index_information()
        if 'user_id_1_message_id_1' not in indexes:
            await self.db.forwarded_messages.create_index([('user_id', 1), ('message_id', 1)], unique=True)
        indexes = await self.db.forwarded_filenames.index_information()
        if 'user_id_1_filename_1' not in indexes:
            await self.db.forwarded_filenames.create_index([('user_id', 1), ('filename', 1)], unique=True)

    async def save_user_credentials(self, user_id, credentials):
        try:
            # Convert necessary fields to integers
            if 'user_id' in credentials:
                credentials['user_id'] = int(credentials['user_id'])
            if 'api_id' in credentials:
                credentials['api_id'] = int(credentials['api_id'])
            if 'source' in credentials:
                credentials['source'] = int(credentials['source'])
            if 'destination' in credentials:
                credentials['destination'] = int(credentials['destination'])
            if 'start_id' in credentials:
                credentials['start_id'] = int(credentials['start_id'])
            if 'end_id' in credentials:
                credentials['end_id'] = int(credentials['end_id'])
            if 'current_id' in credentials:
                credentials['current_id'] = int(credentials['current_id'])
            if 'messages_forwarded' in credentials:
                credentials['messages_forwarded'] = int(credentials['messages_forwarded'])

            users_collection = self.db.users
            await users_collection.update_one(
                {'user_id': user_id},
                {'$set': credentials},
                upsert=True
            )
            logger.info(f"Saved credentials for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save user credentials: {str(e)}", exc_info=True)
            raise

    async def get_user_credentials(self, user_id):
        try:
            users_collection = self.db.users
            user_data = await users_collection.find_one({'user_id': user_id})
            if user_data:
                # Ensure the fields are returned as integers
                if 'user_id' in user_data:
                    user_data['user_id'] = int(user_data['user_id'])
                if 'api_id' in user_data:
                    user_data['api_id'] = int(user_data['api_id'])
                if 'source' in user_data:
                    user_data['source'] = int(user_data['source'])
                if 'destination' in user_data:
                    user_data['destination'] = int(user_data['destination'])
                if 'start_id' in user_data:
                    user_data['start_id'] = int(user_data['start_id'])
                if 'end_id' in user_data:
                    user_data['end_id'] = int(user_data['end_id'])
                if 'current_id' in user_data:
                    user_data['current_id'] = int(user_data['current_id'])
                if 'messages_forwarded' in user_data:
                    user_data['messages_forwarded'] = int(user_data['messages_forwarded'])
            return user_data
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
