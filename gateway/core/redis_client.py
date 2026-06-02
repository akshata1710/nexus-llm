import redis.asyncio as redis
from core.config import settings
import logging

logger = logging.getLogger(__name__)

_redis_client = None


async def init_redis():
    global _redis_client
    _redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    await _redis_client.ping()
    logger.info("Redis connected")


def get_redis():
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client