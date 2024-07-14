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

    async def connect(self):
        pass

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
