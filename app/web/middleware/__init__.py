"""FastAPI middleware."""

from __future__ import annotations

from app.web.middleware.prometheus import PrometheusMiddleware

__all__ = ["PrometheusMiddleware"]
