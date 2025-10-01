"""Ozon API client.

Thin wrapper around BaseHTTPClient for Ozon-specific endpoints.
"""

from __future__ import annotations

from typing import Any

from app.clients.http import BaseHTTPClient


class OzonClient:
    """Ozon API client."""

    def __init__(
        self,
        client_id: str,
        api_key: str,
        base_url: str = "https://api-seller.ozon.ru",
        rate_limit_per_min: int = 300,
    ):
        """Initialize Ozon client.

        Args:
            client_id: Ozon Client-Id
            api_key: Ozon API key
            base_url: Base URL for Ozon API
            rate_limit_per_min: Request rate limit per minute

        """
        headers = {
            "Client-Id": client_id,
            "Api-Key": api_key,
            "Content-Type": "application/json",
        }
        self.http = BaseHTTPClient(
            base_url,
            default_headers=headers,
            rate_limit_per_min=rate_limit_per_min,
        )

    async def finance_transactions(
        self, date_from: str, date_to: str, page: int = 1, page_size: int = 100
    ) -> dict[str, Any]:
        """Get financial transactions from Ozon.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            page: Page number
            page_size: Items per page

        Returns:
            Transaction data

        """
        body = {
            "filter": {"date": {"from": date_from, "to": date_to}},
            "page": page,
            "page_size": page_size,
        }
        return await self.http.json("POST", "/v3/finance/transaction/list", json_body=body)

    async def close(self) -> None:
        """Close HTTP client session."""
        await self.http.close()


__all__ = ["OzonClient"]
