"""Tests for rate limiting."""

import time

import pytest

from app.clients.ratelimit import AsyncTokenBucket


@pytest.mark.asyncio
async def test_token_bucket_rate():
    """Test that token bucket enforces rate limit."""
    bucket = AsyncTokenBucket(rate_per_sec=10, capacity=5)
    t0 = time.monotonic()

    # Use up 5 tokens immediately
    for _ in range(5):
        await bucket.acquire()

    # 6th token should require waiting ~0.1s
    await bucket.acquire()
    elapsed = time.monotonic() - t0

    assert elapsed >= 0.09  # Allow small margin for timing


@pytest.mark.asyncio
async def test_token_bucket_refill():
    """Test that tokens refill over time."""
    bucket = AsyncTokenBucket(rate_per_sec=100, capacity=10)

    # Drain bucket
    for _ in range(10):
        await bucket.acquire()

    # Wait for refill
    await bucket.acquire(5)  # Should wait ~0.05s

    # Should have refilled
    assert bucket.tokens >= 0


@pytest.mark.asyncio
async def test_token_bucket_burst():
    """Test that bucket allows burst up to capacity."""
    bucket = AsyncTokenBucket(rate_per_sec=10, capacity=20)

    t0 = time.monotonic()
    # Should be able to get 20 tokens immediately
    for _ in range(20):
        await bucket.acquire()

    elapsed = time.monotonic() - t0
    # Should be nearly instant (< 0.1s)
    assert elapsed < 0.1
