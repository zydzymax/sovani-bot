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

    async def transactions(
        self, date_from: str, date_to: str, page: int = 1, page_size: int = 1000
    ) -> dict[str, Any]:
        """Get financial transactions from Ozon.

        Endpoint: /v3/finance/transaction/list
        Docs: https://docs.ozon.ru/api/seller/#operation/FinanceAPI_FinanceTransactionListV3

        Args:
            date_from: Start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            date_to: End date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            page: Page number (1-indexed)
            page_size: Items per page (max 1000)

        Returns:
            Transaction data with operations list

        """
        body = {
            "filter": {"date": {"from": date_from, "to": date_to}},
            "page": page,
            "page_size": page_size,
        }
        return await self.http.json("POST", "/v3/finance/transaction/list", json_body=body)

    async def stocks(
        self, limit: int = 1000, offset: int = 0, warehouse_type: str = "ALL"
    ) -> dict[str, Any]:
        """Get warehouse stocks from Ozon (FBO/FBS).

        Endpoint: /v2/analytics/stock_on_warehouses
        Docs: https://docs.ozon.ru/api/seller/#operation/AnalyticsAPI_AnalyticsStockOnWarehouses

        Args:
            limit: Items per page (max 1000)
            offset: Offset for pagination
            warehouse_type: Warehouse type filter (ALL, FBO, FBS, CROSSBORDER)

        Returns:
            Stock data with rows list containing:
            - sku: Ozon SKU ID
            - warehouse_name: Warehouse name
            - item_code: Seller's article
            - item_name: Product name
            - free_to_sell_amount: Available quantity
            - promised_amount: Reserved for shipment
            - reserved_amount: Reserved in orders

        """
        body = {
            "limit": limit,
            "offset": offset,
            "warehouse_type": warehouse_type,
        }
        return await self.http.json("POST", "/v2/analytics/stock_on_warehouses", json_body=body)

    async def finance_transactions(
        self, date_from: str, date_to: str, page: int = 1, page_size: int = 100
    ) -> dict[str, Any]:
        """Alias for transactions() for backward compatibility."""
        return await self.transactions(date_from, date_to, page, page_size)

    async def close(self) -> None:
        """Close HTTP client session."""
        await self.http.close()


__all__ = ["OzonClient"]
