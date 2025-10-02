"""Wildberries API response normalizers.

Functions to normalize WB API responses into standardized dict format
for database ingestion.

All dates converted to UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone


def norm_sales(rows: list[dict]) -> list[dict]:
    """Normalize WB sales API response.

    Input fields (may vary):
    - date, saleID, nmId, supplierArticle, quantity, sum, forPay
    - returnQty, returnAmount, warehouseName, warehouseType
    - acquiringCommission, deliveryRub, commissionRub

    Output format:
    - d (date UTC), sku_key (str), warehouse (str)
    - qty (int), revenue (float), ret_qty (int), ret_amt (float)
    - promo (float), del_cost (float), comm (float), channel (str|None)
    """
    out = []
    for r in rows:
        # Parse date (WB returns ISO with Z)
        date_str = r.get("date", "")
        if date_str:
            d_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        else:
            continue  # Skip records without date

        # SKU identifier (nmId is primary for WB)
        sku_key = str(r.get("nmId") or r.get("nmid") or r.get("supplierArticle") or "")
        if not sku_key:
            continue  # Skip records without SKU

        # Warehouse
        warehouse = r.get("warehouseName") or r.get("warehouse") or ""

        # Quantities
        qty = int(r.get("quantity") or r.get("saleQty") or 0)
        ret_qty = int(r.get("returnQty") or 0)

        # Revenue (WB uses different fields)
        revenue = float(r.get("forPay") or r.get("sum") or r.get("finishedPrice") or 0.0)
        ret_amt = float(r.get("returnAmount") or 0.0)

        # Costs/fees
        promo = float(r.get("acquiringCommission") or r.get("promoCost") or 0.0)
        del_cost = float(r.get("deliveryRub") or 0.0)
        comm = float(r.get("commissionRub") or 0.0)

        # Channel (FBO/FBS)
        channel = r.get("warehouseType") or None

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


def norm_stocks(rows: list[dict]) -> list[dict]:
    """Normalize WB stocks API response.

    Input fields (may vary):
    - nmId, supplierArticle, quantity, stock, warehouseName
    - inWayToClient, inWayFromClient

    Output format:
    - d (date UTC - snapshot date), sku_key (str), warehouse (str)
    - on_hand (int), in_transit (int)
    """
    out = []
    snapshot_date = datetime.now(timezone.utc).date()  # Current UTC date

    for r in rows:
        # SKU identifier
        sku_key = str(r.get("nmId") or r.get("nmid") or r.get("supplierArticle") or "")
        if not sku_key:
            continue

        # Warehouse
        warehouse = r.get("warehouseName") or r.get("warehouse") or ""

        # Stock quantities
        on_hand = int(r.get("quantity") or r.get("stock") or 0)
        in_transit = int(r.get("inWayToClient") or 0) + int(r.get("inWayFromClient") or 0)

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


def norm_feedbacks(rows: list[dict]) -> list[dict]:
    """Normalize WB feedbacks API response.

    Input fields (may vary):
    - id, createdDate, createdAt, nmId, productValuation, rating
    - text, comment, media, answer (existing reply)

    Output format:
    - review_id (str), marketplace ("WB"), sku_key (str)
    - created_at_utc (datetime), rating (int), has_media (bool), text (str)
    - reply_status (str|None), reply_text (str|None)
    """
    out = []

    for r in rows:
        # Review ID
        review_id = str(r.get("id") or "")
        if not review_id:
            continue

        # Parse creation date
        created = r.get("createdDate") or r.get("createdAt") or ""
        if created:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            created_at_utc = dt.replace(tzinfo=timezone.utc)
        else:
            created_at_utc = datetime.now(timezone.utc)

        # SKU
        sku_key = str(r.get("nmId") or r.get("nmid") or "")

        # Rating
        rating = int(r.get("productValuation") or r.get("rating") or 0)

        # Media
        has_media = bool(r.get("media") or r.get("photoLinks") or False)

        # Text
        text = r.get("text") or r.get("comment") or ""

        # Reply status (if answer exists)
        answer = r.get("answer") or {}
        reply_status = "sent" if answer.get("text") else None
        reply_text = answer.get("text") if answer else None

        out.append(
            {
                "review_id": review_id,
                "marketplace": "WB",
                "sku_key": sku_key,
                "created_at_utc": created_at_utc,
                "rating": rating,
                "has_media": has_media,
                "text": text,
                "reply_status": reply_status,
                "reply_text": reply_text,
            }
        )

    return out
