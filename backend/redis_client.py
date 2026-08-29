import os
import redis
import logging

logger = logging.getLogger(__name__)

_redis_client = None

class MemoryRedis:
    def __init__(self):
        self.store = {}
    def ping(self):
        return True
    def setex(self, key, time, value):
        import time as t
        self.store[key] = (value, t.time() + time)
    def get(self, key):
        import time as t
        if key in self.store:
            val, exp = self.store[key]
            if t.time() < exp:
                return val
            else:
                del self.store[key]
        return None
    def delete(self, *keys):
        """Match redis-py semantics: remove keys, return how many were deleted."""
        removed = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                removed += 1
        return removed

_warned_memory = False

def get_redis():
    global _redis_client, _warned_memory
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except (redis.ConnectionError, Exception):
            pass  # Try to reconnect

    redis_url = os.getenv("REDIS_URL")
    is_production = os.getenv("FLASK_ENV") == "production"

    if redis_url == "memory://":
        if is_production:
            # In-memory storage does NOT share state across gunicorn/uwsgi
            # workers -> token revocation and rate limiting become unreliable.
            raise RuntimeError(
                "FATAL: REDIS_URL=memory:// is only allowed for single-process "
                "local development. Set a real REDIS_URL in production."
            )
        if not _warned_memory:
            logger.warning(
                "Using MemoryRedis fallback (REDIS_URL=memory://). This is "
                "single-process ONLY - token revocation/rate limits will NOT "
                "work across multiple workers."
            )
            _warned_memory = True
        if not isinstance(_redis_client, MemoryRedis):
            _redis_client = MemoryRedis()
        return _redis_client
    elif redis_url:
        try:
            # decode_responses=True makes it return strings instead of bytes
            _redis_client = redis.from_url(redis_url, decode_responses=True)
            _redis_client.ping()
            return _redis_client
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
            if is_production:
                raise RuntimeError(f"FATAL: Redis is required in production but unreachable: {e}")
            _redis_client = None

    return None

