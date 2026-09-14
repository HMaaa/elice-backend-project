from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis: Redis = from_url(get_settings().redis_url, decode_responses=True)


def get_redis() -> Redis:
    return _redis
