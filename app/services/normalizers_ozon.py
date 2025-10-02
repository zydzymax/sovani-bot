"""Ozon API response normalizers.

Functions to normalize Ozon API responses into standardized dict format
for database ingestion.

All dates converted to UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime


def norm_transactions(resp: dict) -> list[dict]:
    """Normalize Ozon finance/transaction/list API response.

    Input structure:
    {
        "result": {
            "operations": [
                {
                    "operation_date": "2025-01-01T12:00:00Z",
                    "operation_type": "sale" | "refund" | "payout" | ...,
                    "operation_summ": 1000.0,
                    "operation_id": "123456",
                    "posting": {...},
                    "items": [...]
                }
            ]
        }
    }

    Output format:
    - d (date UTC), marketplace ("OZON"), type (str)
    - amount (float), ref_id (str)
    """
    out = []

    operations = resp.get("result", {}).get("operations", [])

    for r in operations:
        # Parse date
        date_str = r.get("operation_date", "")
        if date_str:
            d_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        else:
            continue

        # Type
        op_type = r.get("operation_type") or r.get("type") or ""

        # Amount
        amount = float(r.get("operation_summ") or r.get("accruals_for_sale") or 0.0)

        # Reference ID
        ref_id = str(r.get("operation_id") or r.get("posting_number") or "")

        out.append(
            {
                "d": d_utc,
                "marketplace": "OZON",
                "type": op_type,
                "amount": amount,
                "ref_id": ref_id,
            }
        )

    return out


def norm_stocks(resp: dict) -> list[dict]:
    """Normalize Ozon warehouse/stock API response.

    Input structure:
    {
        "result": {
            "rows": [
                {
                    "offer_id": "ARTICLE-123",
                    "product_id": 456789,
                    "warehouse_name": "Moscow",
                    "free_to_sell_amount": 10,
                    "in_way_to_client": 5,
                    "in_way_from_client": 2,
                    "reserved_amount": 3
                }
            ]
        }
    }

    Output format:
    - d (date UTC - snapshot date), sku_key (str), warehouse (str)
    - on_hand (int), in_transit (int)
    """
    out = []
    snapshot_date = datetime.now(UTC).date()

    rows = resp.get("result", {}).get("rows", [])

    for r in rows:
        # SKU identifier (Ozon uses offer_id or product_id)
        sku_key = str(r.get("offer_id") or r.get("product_id") or "")
        if not sku_key:
            continue

        # Warehouse
        warehouse = r.get("warehouse_name") or ""

        # Stock quantities
        on_hand = int(r.get("free_to_sell_amount") or r.get("present") or 0)
        in_transit = int(r.get("in_way_to_client") or 0) + int(r.get("in_way_from_client") or 0)

        out.append(
            {
                "d": snapshot_date,
                "sku_key": sku_key,
                "warehouse": warehouse,
                "on_hand": on_hand,
                "in_transit": in_transit,
            }
        )

    return out


def norm_sales_from_transactions(resp: dict) -> list[dict]:
    """Extract sales data from Ozon transactions.

    Ozon doesn't have separate sales endpoint - sales are in transactions
    with type "sale" or similar.

    Output format:
    - d (date UTC), sku_key (str), warehouse (str)
    - qty (int), revenue (float), ret_qty (int), ret_amt (float)
    - promo (float), del_cost (float), comm (float), channel (str|None)
    """
    out = []

    operations = resp.get("result", {}).get("operations", [])

    for op in operations:
        op_type = op.get("operation_type", "")

        # Process only sales and refunds
        if op_type not in ["sale", "refund", "ClientReturnAgentOperation"]:
            continue

        # Parse date
        date_str = op.get("operation_date", "")
        if date_str:
            d_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        else:
            continue

        # Get posting details
        posting = op.get("posting", {})
        items = op.get("items", [])

        # Warehouse
        warehouse = posting.get("warehouse_name") or op.get("warehouse_name") or ""

        # Process each item in the operation
        for item in items:
            sku_key = str(item.get("sku") or item.get("offer_id") or "")
            if not sku_key:
                continue

            qty = 0
            ret_qty = 0

            if op_type == "sale":
                qty = int(item.get("quantity") or 0)
            elif op_type in ["refund", "ClientReturnAgentOperation"]:
                ret_qty = int(item.get("quantity") or 0)

            # Revenue calculation (Ozon has complex structure)
            revenue = float(
                op.get("accruals_for_sale")
                or item.get("price")
                or item.get("commission_amount")
                or 0.0
            )
            ret_amt = float(item.get("return_amount") or 0.0) if ret_qty > 0 else 0.0

            # Costs
            promo = float(item.get("marketing_actions") or 0.0)
            del_cost = float(op.get("delivery_charge") or 0.0)
            comm = float(
                op.get("sale_commission")
                or item.get("commission_amount")
                or item.get("commissions_amount")
                or 0.0
            )

            # Channel (Ozon mostly FBO)
            channel = "FBO"

            out.append(
                {
                    "d": d_utc,
                    "sku_key": sku_key,
                    "warehouse": warehouse,
                    "qty": qty,
                    "revenue": revenue,
                    "ret_qty": ret_qty,
                    "ret_amt": ret_amt,
                    "promo": promo,
                    "del_cost": del_cost,
                    "comm": comm,
                    "channel": channel,
                }
            )

    return out
