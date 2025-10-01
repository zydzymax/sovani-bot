"""Asynchronous token bucket rate limiter.

Provides token bucket algorithm for rate limiting with async support.
"""

from __future__ import annotations

import asyncio
import time


class AsyncTokenBucket:
    """Simple token-bucket with time-based refill (async)."""

    def __init__(self, rate_per_sec: float, capacity: int):
        """Initialize token bucket.

        Args:
            rate_per_sec: Token refill rate per second
            capacity: Maximum number of tokens

        """
        self.rate = rate_per_sec
        self.capacity = capacity
        self.tokens = float(capacity)
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from bucket, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        """
        async with self._lock:
            now = time.monotonic()
            # Refill tokens based on elapsed time
            delta = now - self.updated
            self.updated = now
            self.tokens = min(self.capacity, self.tokens + delta * self.rate)

            # Wait if not enough tokens
            if self.tokens < tokens:
                need = tokens - self.tokens
                wait_sec = need / self.rate
                await asyncio.sleep(wait_sec)
                self.tokens = 0.0
            else:
                self.tokens -= tokens


__all__ = ["AsyncTokenBucket"]
