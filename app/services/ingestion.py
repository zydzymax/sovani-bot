"""Data ingestion services for WB/Ozon APIs.

Idempotent data collection services that:
1. Fetch data from WB/Ozon APIs
2. Normalize and aggregate by day
3. Upsert into database using src_hash for idempotency

All dates stored in UTC.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import DailySales, SKU, Warehouse

log = get_logger("sovani_bot.ingestion")


def _hash_payload(payload: dict) -> str:
    """Generate SHA256 hash of payload for idempotency checks."""
    # Stable JSON serialization (sorted keys)
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def ensure_sku(
    db: Session,
    marketplace: str,
    nm_id: str | None = None,
    ozon_id: str | None = None,
    article: str | None = None,
) -> int:
    """Get or create SKU record.

    Args:
        db: Database session
        marketplace: "WB" or "OZON"
        nm_id: Wildberries nmId
        ozon_id: Ozon product_id
        article: Seller article

    Returns:
        SKU id
    """
    # Try to find existing SKU
    stmt = select(SKU).where(SKU.marketplace == marketplace)

    if marketplace == "WB" and nm_id:
        stmt = stmt.where(SKU.nm_id == nm_id)
    elif marketplace == "OZON" and ozon_id:
        stmt = stmt.where(SKU.ozon_id == ozon_id)
    else:
        # Fallback to article
        stmt = stmt.where(SKU.article == article)

    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        return existing.id

    # Create new SKU
    new_sku = SKU(
        marketplace=marketplace,
        nm_id=nm_id,
        ozon_id=ozon_id,
        article=article,
    )
    db.add(new_sku)
    db.flush()  # Get ID without committing
    return new_sku.id


def ensure_warehouse(db: Session, marketplace: str, code: str, name: str | None = None) -> int:
    """Get or create Warehouse record.

    Args:
        db: Database session
        marketplace: "WB" or "OZON"
        code: Warehouse code
        name: Warehouse name (optional)

    Returns:
        Warehouse id
    """
    # Try to find existing warehouse
    stmt = select(Warehouse).where(Warehouse.marketplace == marketplace, Warehouse.code == code)
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        return existing.id

    # Create new warehouse
    new_wh = Warehouse(marketplace=marketplace, code=code, name=name)
    db.add(new_wh)
    db.flush()
    return new_wh.id


def collect_wb_sales_stub(db: Session, d_from: date, d_to: date) -> int:
    """Collect WB sales data (STUB for Stage 7).

    This is a placeholder that shows the pattern. Real implementation
    will call WBClient and normalize API response.

    Args:
        db: Database session
        d_from: Start date (UTC)
        d_to: End date (UTC)

    Returns:
        Number of upserted records
    """
    log.info("wb_sales_collection_started", extra={"from": str(d_from), "to": str(d_to)})

    upserts = 0

    # STUB: In real implementation, call:
    # client = WBClient(token=settings.wb_stats_token)
    # data = await client.sales(date_from=d_from.isoformat(), flag=0)
    # rows = normalize_wb_sales(data)

    # Example stub data (for testing schema)
    stub_rows = [
        {
            "d": d_from,
            "nm_id": "12345678",
            "article": "TEST-ARTICLE-1",
            "warehouse_code": "Коледино",
            "qty": 10,
            "revenue_gross": 15000.0,
            "refunds_qty": 1,
            "refunds_amount": 1500.0,
            "promo_cost": 500.0,
            "delivery_cost": 200.0,
            "commission_amount": 1800.0,
            "channel": "FBO",
        }
    ]

    for row in stub_rows:
        # Ensure SKU and Warehouse exist
        sku_id = ensure_sku(db, "WB", nm_id=row["nm_id"], article=row["article"])
        wh_id = ensure_warehouse(db, "WB", row["warehouse_code"])

        # Prepare payload for hashing
        payload = {
            "d": str(row["d"]),
            "sku_id": sku_id,
            "warehouse_id": wh_id,
            "qty": row["qty"],
            "revenue_gross": row["revenue_gross"],
            "refunds_qty": row["refunds_qty"],
            "refunds_amount": row["refunds_amount"],
            "promo_cost": row["promo_cost"],
            "delivery_cost": row["delivery_cost"],
            "commission_amount": row["commission_amount"],
            "channel": row["channel"],
        }
        src_hash = _hash_payload(payload)

        # Upsert with idempotency check
        stmt = insert(DailySales).values(
            d=row["d"],
            sku_id=sku_id,
            warehouse_id=wh_id,
            qty=row["qty"],
            revenue_gross=row["revenue_gross"],
            refunds_qty=row["refunds_qty"],
            refunds_amount=row["refunds_amount"],
            promo_cost=row["promo_cost"],
            delivery_cost=row["delivery_cost"],
            commission_amount=row["commission_amount"],
            channel=row["channel"],
            src_hash=src_hash,
        )

        # PostgreSQL: on_conflict_do_update with WHERE clause
        # SQLite: on_conflict_do_update without WHERE (for testing)
        if db.bind.dialect.name == "postgresql":
            stmt = stmt.on_conflict_do_update(
                index_elements=["d", "sku_id", "warehouse_id"],
                set_=dict(
                    qty=stmt.excluded.qty,
                    revenue_gross=stmt.excluded.revenue_gross,
                    refunds_qty=stmt.excluded.refunds_qty,
                    refunds_amount=stmt.excluded.refunds_amount,
                    promo_cost=stmt.excluded.promo_cost,
                    delivery_cost=stmt.excluded.delivery_cost,
                    commission_amount=stmt.excluded.commission_amount,
                    channel=stmt.excluded.channel,
                    src_hash=stmt.excluded.src_hash,
                ),
                where=(DailySales.src_hash != stmt.excluded.src_hash),
            )
        else:
            # SQLite: simpler upsert (always update)
            stmt = stmt.on_conflict_do_update(
                index_elements=["d", "sku_id", "warehouse_id"],
                set_=dict(
                    qty=stmt.excluded.qty,
                    revenue_gross=stmt.excluded.revenue_gross,
                    refunds_qty=stmt.excluded.refunds_qty,
                    refunds_amount=stmt.excluded.refunds_amount,
                    promo_cost=stmt.excluded.promo_cost,
                    delivery_cost=stmt.excluded.delivery_cost,
                    commission_amount=stmt.excluded.commission_amount,
                    channel=stmt.excluded.channel,
                    src_hash=stmt.excluded.src_hash,
                ),
            )

        db.execute(stmt)
        upserts += 1

    db.commit()

    log.info(
        "wb_sales_collection_completed",
        extra={"upserts": upserts, "from": str(d_from), "to": str(d_to)},
    )

    return upserts


# TODO Stage 8: Implement real WB/Ozon collection functions
# - collect_wb_sales(db, d_from, d_to) -> int
# - collect_wb_stock(db, d: date) -> int
# - collect_ozon_sales(db, d_from, d_to) -> int
# - collect_ozon_stock(db, d: date) -> int
# - collect_ozon_cashflows(db, d_from, d_to) -> int
