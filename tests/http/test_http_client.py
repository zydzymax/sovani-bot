"""Tests for BaseHTTPClient with retry logic."""

import pytest

from app.clients.http import BaseHTTPClient


@pytest.mark.asyncio
async def test_base_client_initialization():
    """Test that BaseHTTPClient initializes correctly."""
    client = BaseHTTPClient(
        "https://example.com",
        default_headers={"X-Test": "value"},
        rate_limit_per_min=60,
    )

    assert client.base_url == "https://example.com"
    assert client.default_headers == {"X-Test": "value"}
    assert client._rate is not None

    await client.close()


@pytest.mark.asyncio
async def test_base_client_without_rate_limit():
    """Test client without rate limiting."""
    client = BaseHTTPClient("https://example.com", rate_limit_per_min=None)

    assert client._rate is None

    await client.close()


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_requests():
    """Test that circuit breaker blocks requests when open."""
    client = BaseHTTPClient(
        "https://example.com",
        cb_fail_threshold=0,  # Open immediately
    )

    # Manually open circuit breaker
    for _ in range(10):
        client._cb.on_failure()

    # Should raise RuntimeError when circuit is open
    with pytest.raises(RuntimeError, match="CircuitBreaker is OPEN"):
        await client.request("GET", "/test")

    await client.close()


def test_retry_status_codes():
    """Test that RETRY_STATUS contains expected codes."""
    from app.clients.http import RETRY_STATUS

    assert 429 in RETRY_STATUS  # Too Many Requests
    assert 500 in RETRY_STATUS  # Internal Server Error
    assert 502 in RETRY_STATUS  # Bad Gateway
    assert 503 in RETRY_STATUS  # Service Unavailable
    assert 504 in RETRY_STATUS  # Gateway Timeout
