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

    async def get_sales(self, date_from: str, flag: int = 0) -> dict[str, Any]:
        """Get sales data from WB.

        Endpoint: /api/v1/supplier/sales
        Docs: https://openapi.wildberries.ru/#tag/Statistika/paths/~1api~1v1~1supplier~1sales/get

        Args:
            date_from: Start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            flag: 0 - data for last 7 days, 1 - data for all time (up to 176 days)

        Returns:
            List of sales records in API format

        """
        return await self.http.json(
            "GET", "/api/v1/supplier/sales", params={"dateFrom": date_from, "flag": flag}
        )

    async def get_stocks(self, date_from: str) -> dict[str, Any]:
        """Get stocks data from WB.

        Endpoint: /api/v1/supplier/stocks
        Docs: https://openapi.wildberries.ru/#tag/Statistika/paths/~1api~1v1~1supplier~1stocks/get

        Args:
            date_from: Start date (YYYY-MM-DD)

        Returns:
            List of stock records in API format

        """
        return await self.http.json(
            "GET", "/api/v1/supplier/stocks", params={"dateFrom": date_from}
        )

    async def get_incomes(self, date_from: str) -> dict[str, Any]:
        """Get incoming supplies from WB.

        Endpoint: /api/v1/supplier/incomes
        Docs: https://openapi.wildberries.ru/#tag/Statistika/paths/~1api~1v1~1supplier~1incomes/get

        Args:
            date_from: Start date (YYYY-MM-DD)

        Returns:
            List of income records in API format

        """
        return await self.http.json(
            "GET", "/api/v1/supplier/incomes", params={"dateFrom": date_from}
        )

    async def sales(self, date_from: str, flag: int = 0) -> dict[str, Any]:
        """Alias for get_sales() for backward compatibility."""
        return await self.get_sales(date_from, flag)

    async def close(self) -> None:
        """Close HTTP client session."""
        await self.http.close()


__all__ = ["WBClient"]
