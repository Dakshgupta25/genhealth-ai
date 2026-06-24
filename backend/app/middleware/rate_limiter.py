"""
Rate limiting middleware.

Implements a sliding-window rate limiter backed by Redis.
Limits are configurable per route via the `rate_limit` dependency.

Default: 100 requests / 60 seconds per IP address.
"""

import logging
import time
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.config import get_settings
from app.database import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()


async def check_rate_limit(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
    limit: int = None,
    window: int = 60,
) -> None:
    """
    Sliding-window rate limiter using Redis INCR + EXPIRE.

    Each unique (IP + path) combination gets its own counter with a TTL.
    When the counter exceeds `limit`, a 429 is returned.

    Args:
        request: The incoming FastAPI request.
        redis:   Redis client (injected via dependency).
        limit:   Max requests per `window` seconds. Defaults to settings value.
        window:  Time window in seconds (default 60).

    Raises:
        HTTP 429 Too Many Requests when the limit is exceeded.
    """
    if limit is None:
        limit = settings.RATE_LIMIT_PER_MINUTE

    client_ip = request.client.host if request.client else "unknown"
    route_path = request.url.path

    # Key includes IP and route for per-endpoint limits
    rate_key = f"rate:{client_ip}:{route_path}"

    try:
        current_count = await redis.incr(rate_key)

        # Set expiry only on the first request in the window
        if current_count == 1:
            await redis.expire(rate_key, window)

        # Remaining requests to include in response header (set by caller)
        remaining = max(0, limit - current_count)

        if current_count > limit:
            # Get the TTL so we can advise the client when to retry
            ttl = await redis.ttl(rate_key)
            logger.warning(
                "Rate limit exceeded: ip=%s path=%s count=%d limit=%d",
                client_ip, route_path, current_count, limit
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "success": False,
                    "error": f"Rate limit exceeded. Try again in {ttl} seconds.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": ttl,
                },
                headers={"Retry-After": str(ttl)},
            )

    except HTTPException:
        raise
    except Exception as exc:
        # If Redis is down, fail open (don't block legitimate traffic)
        logger.error("Rate limiter Redis error (failing open): %s", exc)


def rate_limit(limit: int = None, window: int = 60):
    """
    Dependency factory for per-route rate limits.

    Usage:
        @router.post("/login", dependencies=[Depends(rate_limit(limit=5, window=60))])
        async def login():
            ...

    Args:
        limit:  Max requests per window. Defaults to global setting.
        window: Time window in seconds.
    """
    async def _check(
        request: Request,
        redis: aioredis.Redis = Depends(get_redis),
    ) -> None:
        await check_rate_limit(request, redis, limit=limit, window=window)

    return _check


# ─── Pre-configured rate limiters ────────────────────────────────────────────

# Strict: for auth endpoints (login, signup)
strict_rate_limit = rate_limit(limit=10, window=60)

# Standard: default for most authenticated endpoints
standard_rate_limit = rate_limit(limit=100, window=60)

# Loose: for public read endpoints
loose_rate_limit = rate_limit(limit=200, window=60)
