"""Prometheus metrics middleware for FastAPI."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics for HTTP requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        method = request.method
        path = request.url.path

        # Normalize path (replace IDs with placeholders)
        endpoint = self._normalize_path(path)

        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        # Measure request duration
        start_time = time.time()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            # Track failed requests
            http_requests_total.labels(
                method=method, endpoint=endpoint, status="500"
            ).inc()
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
            raise
        finally:
            duration = time.time() - start_time
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
                duration
            )

        # Track completed requests
        http_requests_total.labels(
            method=method, endpoint=endpoint, status=str(status)
        ).inc()
        http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders.

        Examples:
            /api/v1/reviews/REV123/reply -> /api/v1/reviews/{id}/reply
            /api/v1/advice?date=2025-01-15 -> /api/v1/advice
        """
        # Remove query parameters
        path = path.split("?")[0]

        # Replace common ID patterns
        parts = path.split("/")
        normalized = []
        for i, part in enumerate(parts):
            # Skip empty parts
            if not part:
                normalized.append(part)
                continue

            # Check if part looks like an ID
            if (
                part.isdigit()  # Numeric ID
                or (len(part) > 10 and part.isupper())  # Review ID like REV001
                or (i > 0 and parts[i - 1] in ["reviews", "advice", "inventory"])
            ):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)
