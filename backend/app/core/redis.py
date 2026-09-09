import logging
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> Optional[aioredis.Redis]:
    """Provides an asynchronous Redis connection, returning None if Redis is unavailable or disabled."""
    global _redis_client
    if not settings.REDIS_ENABLED:
        return None

    if _redis_client is None:
        try:
            _redis_client = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=2.0,
            )
            # Ping test
            await _redis_client.ping()
        except Exception as e:
            logger.warning("Redis is not reachable, operating in cacheless mode: %s", e)
            _redis_client = None

    return _redis_client


async def close_redis() -> None:
    """Close active Redis connections."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
