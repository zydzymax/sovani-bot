"""Unified async HTTP client with retry, rate limiting, and circuit breaker.

Provides BaseHTTPClient with built-in reliability patterns.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping
from typing import Any

import aiohttp

from app.clients.circuit_breaker import CircuitBreaker
from app.clients.ratelimit import AsyncTokenBucket
from app.core.logging import get_logger

log = get_logger("sovani_bot.http")

DEFAULT_TIMEOUT = 30
RETRY_STATUS = {429, 500, 502, 503, 504}


class BaseHTTPClient:
    """Base HTTP client with retry, rate limiting, and circuit breaker."""

    def __init__(
        self,
        base_url: str,
        default_headers: Mapping[str, str] | None = None,
        timeout_sec: int = DEFAULT_TIMEOUT,
        # Rate limiting and circuit breaker (per host)
        rate_limit_per_min: int | None = None,
        rate_capacity: int | None = None,
        cb_fail_threshold: int = 5,
        cb_reset_timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.75,
        backoff_max: float = 8.0,
    ) -> None:
        """Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            default_headers: Headers to include in all requests
            timeout_sec: Request timeout in seconds
            rate_limit_per_min: Max requests per minute (None to disable)
            rate_capacity: Token bucket capacity (defaults to rate_limit_per_min)
            cb_fail_threshold: Failures before circuit breaker opens
            cb_reset_timeout: Seconds before circuit breaker tries half-open
            max_retries: Maximum retry attempts
            backoff_base: Base delay for exponential backoff
            backoff_max: Maximum backoff delay

        """
        self.base_url = base_url.rstrip("/")
        self.default_headers = dict(default_headers or {})
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

        self._rate: AsyncTokenBucket | None = None
        if rate_limit_per_min:
            rate_per_sec = rate_limit_per_min / 60.0
            cap = rate_capacity or rate_limit_per_min
            self._rate = AsyncTokenBucket(rate_per_sec=rate_per_sec, capacity=cap)

        self._cb = CircuitBreaker(cb_fail_threshold, cb_reset_timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
    ) -> aiohttp.ClientResponse:
        """Make HTTP request with retry, rate limiting, and circuit breaker.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: URL path (relative to base_url)
            headers: Additional headers
            params: Query parameters
            json_body: JSON body for request
            data: Raw data for request

        Returns:
            aiohttp.ClientResponse

        Raises:
            RuntimeError: If circuit breaker is open
            aiohttp.ClientError: If all retries fail

        """
        if not self._cb.allow():
            raise RuntimeError("CircuitBreaker is OPEN for host")

        url = f"{self.base_url}{path}"
        hdrs = dict(self.default_headers)
        if headers:
            hdrs.update(headers)

        # Rate limit (if configured)
        if self._rate:
            await self._rate.acquire(1)

        session = await self._ensure_session()
        attempt = 0

        while True:
            attempt += 1
            t0 = time.perf_counter()

            try:
                async with session.request(
                    method=method.upper(),
                    url=url,
                    headers=hdrs,
                    params=params,
                    json=json_body,
                    data=data,
                ) as resp:
                    elapsed = (time.perf_counter() - t0) * 1000
                    body_size = resp.content_length
                    status = resp.status

                    log.info(
                        "http_response",
                        extra={
                            "method": method,
                            "url": url,
                            "status": status,
                            "elapsed_ms": int(elapsed),
                            "attempt": attempt,
                            "body_len": body_size,
                        },
                    )

                    if status in RETRY_STATUS and attempt < self.max_retries:
                        # Exponential backoff with jitter
                        delay = min(self.backoff_base * (2 ** (attempt - 1)), self.backoff_max)
                        delay *= 0.7 + 0.6 * (time.perf_counter() % 1)  # poor-man jitter
                        await asyncio.sleep(delay)
                        continue

                    # Record success/failure for circuit breaker
                    if 200 <= status < 300:
                        self._cb.on_success()
                    else:
                        self._cb.on_failure()

                    # Read response body before exiting context
                    body = await resp.read()
                    # Create new response-like object with body
                    resp._body = body
                    return resp

            except (TimeoutError, aiohttp.ClientError) as e:
                log.warning(
                    "http_exception",
                    extra={
                        "method": method,
                        "url": url,
                        "attempt": attempt,
                        "error": str(e),
                    },
                )
                self._cb.on_failure()

                if attempt >= self.max_retries:
                    raise

                delay = min(self.backoff_base * (2 ** (attempt - 1)), self.backoff_max)
                delay *= 0.7 + 0.6 * (time.perf_counter() % 1)
                await asyncio.sleep(delay)

    async def json(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request and parse JSON response.

        Args:
            method: HTTP method
            path: URL path
            **kwargs: Additional arguments for request()

        Returns:
            Parsed JSON response

        Raises:
            json.JSONDecodeError: If response is not valid JSON

        """
        resp = await self.request(method, path, **kwargs)
        txt = await resp.text()
        try:
            return json.loads(txt) if txt else {}
        except json.JSONDecodeError:
            log.error(
                "json_decode_error",
                extra={"url": f"{self.base_url}{path}", "text_sample": txt[:256]},
            )
            raise


__all__ = ["BaseHTTPClient", "DEFAULT_TIMEOUT", "RETRY_STATUS"]
