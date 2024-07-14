# database.py
import json
import aiosqlite
import logging
import motor.motor_asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from config import Settings
logger = logging.getLogger(__name__)
class Database(ABC):
    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def save_user_credentials(self, user_id: int, credentials: Dict[str, Any]):
        pass

    @abstractmethod
    async def get_user_credentials(self, user_id: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def setup_message_queue(self):
        pass

    @abstractmethod
    async def get_active_users(self) -> List[int]:
        pass

    @abstractmethod
    async def sync_cache_with_db(self):
        pass

class SQLiteDatabase(Database):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.sqlite_conn = None

    async def connect(self):
        self.sqlite_conn = await aiosqlite.connect(self.db_path)
        await self.sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        logger.info("SQLite connection established.")

    async def disconnect(self):
        if self.sqlite_conn:
            await self.sqlite_conn.close()
            logger.info("SQLite connection closed.")

    async def save_user_credentials(self, user_id: int, credentials: Dict[str, Any]):
        logger.debug(f"Saving credentials for user {user_id}: {credentials}")
        async with self.sqlite_conn.execute(
            "INSERT INTO user_credentials (user_id, credentials) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET credentials=excluded.credentials;",
            (user_id, json.dumps(credentials))
        ) as cursor:
            await self.sqlite_conn.commit()

<<<<<<< HEAD
    async def get_user_credentials(self, user_id: int) -> Dict[str, Any]:
        async with self.sqlite_conn.execute(
            "SELECT credentials FROM user_credentials WHERE user_id = ?;", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                credentials = json.loads(row[0])
                logger.debug(f"Retrieved credentials for user {user_id}: {credentials}")
                return credentials
            else:
                logger.debug(f"No credentials found for user {user_id}")
                return {}

    async def setup_message_queue(self):
        await self.sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS message_queue (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                message TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await self.sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS user_credentials (
                user_id INTEGER PRIMARY KEY,
                credentials TEXT
=======
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
>>>>>>> 495dcb0 (skip duplicate)
            )
        ''')
        await self.sqlite_conn.commit()

    async def get_active_users(self) -> List[int]:
        cursor = await self.sqlite_conn.execute("SELECT user_id FROM user_credentials WHERE forwarding = 1")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def sync_cache_with_db(self):
        pass

class MongoDBDatabase(Database):
    def __init__(self, uri: str, db_name: str):
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.mongo_client[db_name]

<<<<<<< HEAD
    async def connect(self):
        pass
=======
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
>>>>>>> 495dcb0 (skip duplicate)

    async def disconnect(self):
        if self.mongo_client:
            self.mongo_client.close()

    async def save_user_credentials(self, user_id: int, credentials: Dict[str, Any]):
        await self.db.users.update_one({"user_id": user_id}, {"$set": credentials}, upsert=True)

    async def get_user_credentials(self, user_id: int) -> Dict[str, Any]:
        return await self.db.users.find_one({"user_id": user_id})

    async def setup_message_queue(self):
        pass

    async def get_active_users(self) -> List[int]:
        cursor = await self.db.users.find({"active": True}).to_list(None)
        return [doc["user_id"] for doc in cursor]

    async def sync_cache_with_db(self):
        pass

class MongoDBDatabase(Database):
    def __init__(self, uri: str, db_name: str):
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.mongo_client[db_name]

    async def connect(self):
        # MongoDB connects on demand
        pass

    async def disconnect(self):
        if self.mongo_client:
            self.mongo_client.close()

    async def save_user_credentials(self, user_id: int, credentials: Dict[str, Any]):
        await self.db.users.update_one({"user_id": user_id}, {"$set": credentials}, upsert=True)

    async def get_user_credentials(self, user_id: int) -> Dict[str, Any]:
                # Assuming you have implemented the logic to get credentials
        credentials = {}  # Retrieve credentials logic here
        logger.debug(f"Retrieved credentials for user {user_id}: {credentials}")
        return credentials
    async def setup_message_queue(self):
        # Implement MongoDB setup message queue logic if necessary
        pass

    async def get_active_users(self) -> List[int]:
        cursor = await self.db.users.find({"active": True}).to_list(None)
        return [doc["user_id"] for doc in cursor]

    async def sync_cache_with_db(self):
        # Implement sync cache logic
        pass

config = Settings()

if config.SQLITE_DB_PATH:
    db = SQLiteDatabase(config.SQLITE_DB_PATH)
else:
    db = MongoDBDatabase(config.MONGODB_URI, config.DB_NAME)
