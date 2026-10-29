import logging
from typing import AsyncGenerator
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection Pool for Redis
redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20
)

async def get_redis_client() -> aioredis.Redis:
    """Returns a standalone redis client attached to the connection pool."""
    return aioredis.Redis(connection_pool=redis_pool)

async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Dependency that yields a Redis client."""
    client = await get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()

async def check_redis_health() -> bool:
    """Sends a PING command to verify Redis connectivity."""
    try:
        client = await get_redis_client()
        pong = await client.ping()
        await client.aclose()
        return bool(pong)
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False

