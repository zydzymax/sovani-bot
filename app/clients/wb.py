"""Wildberries API client.

Thin wrapper around BaseHTTPClient for WB-specific endpoints.
"""

from __future__ import annotations

from typing import Any

from app.clients.http import BaseHTTPClient


class WBClient:
    """Wildberries API client."""

    def __init__(
        self,
        token: str,
        base_url: str = "https://statistics-api.wildberries.ru",
        rate_limit_per_min: int = 60,
    ):
        """Initialize WB client.

        Args:
            token: WB API token
            base_url: Base URL for WB API
            rate_limit_per_min: Request rate limit per minute

        """
        headers = {"Authorization": token}
        self.http = BaseHTTPClient(
            base_url,
            default_headers=headers,
            rate_limit_per_min=rate_limit_per_min,
        )

    async def sales(self, date_from: str, flag: int = 0) -> dict[str, Any]:
        """Get sales data from WB.

        Args:
            date_from: Start date (YYYY-MM-DD)
            flag: Flag parameter (0 or 1)

        Returns:
            Sales data

        """
        return await self.http.json(
            "GET", "/api/v1/supplier/sales", params={"dateFrom": date_from, "flag": flag}
        )

    async def close(self) -> None:
        """Close HTTP client session."""
        await self.http.close()


__all__ = ["WBClient"]
