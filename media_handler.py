import hashlib
import logging
from typing import Any, Dict
from database import Database

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self, db: Database):
        self.db = db
        self.local_cache = {}

    async def extract_metadata(self, file: Any) -> Dict[str, Any]:
        file_hash = hashlib.sha256(file.bytes).hexdigest()
        file_metadata = {
            'file_id': file.id,
            'size': file.size,
            'hash': file_hash,
            'name': file.name
        }
        return file_metadata

    async def is_file_forwarded(self, file_metadata: Dict[str, Any]) -> bool:
        if file_metadata['hash'] in self.local_cache:
            return True
        result = await self.db.get_file_metadata(file_metadata['hash'])
        if result:
            self.local_cache[file_metadata['hash']] = True
        return result is not None

    async def store_file_metadata(self, file_metadata: Dict[str, Any]):
        await self.db.save_file_metadata(file_metadata)
        self.local_cache[file_metadata['hash']] = True

    async def sync_cache_with_db(self):
        all_metadata = await self.db.get_all_file_metadata()
        self.local_cache = {item['hash']: True for item in all_metadata}
