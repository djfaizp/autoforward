# utils.py
import asyncio
import logging

logger = logging.getLogger(__name__)

async def retry_with_backoff(func, max_retries: int = 5, base_delay: int = 1):
    for retry in range(max_retries):
        try:
            return await func()
        except Exception as e:
            wait_time = base_delay * (2 ** retry)
            logger.warning(f"Retrying in {wait_time} seconds due to error: {str(e)}")
            await asyncio.sleep(wait_time)
    logger.error(f"Max retries reached. Function failed: {func.__name__}")
    raise
