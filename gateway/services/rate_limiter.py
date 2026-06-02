import time
from redis.asyncio import Redis
from fastapi import HTTPException, status


class RateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.
    Tracks requests per minute and tokens per day per user.
    """

    async def check_rpm(self, redis: Redis, user_id: str, limit: int) -> dict:
        """
        Sliding window — requests per minute.
        Key: rate:rpm:<user_id>
        Value: sorted set of timestamps
        """
        key = f"rate:rpm:{user_id}"
        now = time.time()
        window_start = now - 60  # 60 second window

        pipe = redis.pipeline()
        # Remove timestamps outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        # Count requests in window
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Expire key after 2 minutes
        pipe.expire(key, 120)
        results = await pipe.execute()

        current_count = results[1]

        if current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {limit} requests/minute. Try again shortly.",
                headers={"Retry-After": "60"},
            )

        return {
            "limit": limit,
            "remaining": max(0, limit - current_count - 1),
            "window": "60s",
        }

    async def check_tpd(self, redis: Redis, user_id: str, tokens_used: int, limit: int) -> dict:
        """
        Token per day counter using Redis INCRBY with daily expiry.
        Key: rate:tpd:<user_id>:<date>
        """
        from datetime import date
        key = f"rate:tpd:{user_id}:{date.today().isoformat()}"

        current = await redis.incrby(key, tokens_used)
        # Set expiry to 25 hours on first write
        if current == tokens_used:
            await redis.expire(key, 90000)

        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily token limit exceeded: {limit} tokens/day.",
                headers={"Retry-After": "86400"},
            )

        return {
            "limit": limit,
            "used": current,
            "remaining": max(0, limit - current),
            "window": "24h",
        }


rate_limiter = RateLimiter()