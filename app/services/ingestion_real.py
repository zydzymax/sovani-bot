"""Real API integration for data ingestion.

This module replaces the stub version with actual WB/Ozon API calls.
Idempotent data collection with src_hash-based deduplication.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.clients.ozon import OzonClient
from app.clients.wb import WBClient
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Cashflow, DailySales, DailyStock, SKU, Warehouse
from app.services.normalizers_ozon import norm_stocks as norm_ozon_stocks
from app.services.normalizers_ozon import norm_transactions as norm_ozon_transactions
from app.services.normalizers_wb import norm_sales as norm_wb_sales
from app.services.normalizers_wb import norm_stocks as norm_wb_stocks

log = get_logger("sovani_bot.ingestion_real")


def _hash_payload(payload: dict) -> str:
    """Generate SHA256 hash for idempotency."""
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def ensure_sku(
    db: Session,
    marketplace: str,
    nm_id: str | None = None,
    ozon_id: str | None = None,
    article: str | None = None,
) -> int:
    """Get or create SKU."""
    stmt = select(SKU).where(SKU.marketplace == marketplace)

    if marketplace == "WB" and nm_id:
        stmt = stmt.where(SKU.nm_id == nm_id)
    elif marketplace == "OZON" and ozon_id:
        stmt = stmt.where(SKU.ozon_id == ozon_id)
    elif article:
        stmt = stmt.where(SKU.article == article)
    else:
        # Create with minimal info
        new_sku = SKU(marketplace=marketplace, nm_id=nm_id, ozon_id=ozon_id, article=article)
        db.add(new_sku)
        db.flush()
        return new_sku.id

    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        return existing.id

    new_sku = SKU(marketplace=marketplace, nm_id=nm_id, ozon_id=ozon_id, article=article)
    db.add(new_sku)
    db.flush()
    return new_sku.id


def ensure_warehouse(db: Session, marketplace: str, code: str, name: str | None = None) -> int:
    """Get or create Warehouse."""
    stmt = select(Warehouse).where(Warehouse.marketplace == marketplace, Warehouse.code == code)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        return existing.id

    new_wh = Warehouse(marketplace=marketplace, code=code, name=name)
    db.add(new_wh)
    db.flush()
    return new_wh.id


async def collect_wb_sales_range(db: Session, d_from: date, d_to: date) -> int:
    """Collect WB sales for date range.

    Uses flag=0 for last 7 days, flag=1 for all available data (up to 176 days).
    """
    settings = get_settings()
    client = WBClient(token=settings.wb_stats_token)

    log.info("wb_sales_collection_started", extra={"from": str(d_from), "to": str(d_to)})

    try:
        # WB API limitation: flag=0 gives last 7 days, flag=1 gives all data
        # For d_from > 7 days ago, use flag=1
        days_back = (date.today() - d_from).days
        flag = 1 if days_back > 7 else 0

        # Get sales data
        response = await client.get_sales(date_from=d_from.isoformat(), flag=flag)

        # Normalize response
        rows = norm_wb_sales(response if isinstance(response, list) else [])

        # Filter to date range
        rows = [r for r in rows if d_from <= r["d"] <= d_to]

        upserts = 0
        for row in rows:
            sku_id = ensure_sku(db, "WB", nm_id=row["sku_key"])
            wh_id = ensure_warehouse(db, "WB", row["warehouse"]) if row["warehouse"] else None

            payload = {
                "d": str(row["d"]),
                "sku_id": sku_id,
                "warehouse_id": wh_id,
                "qty": row["qty"],
                "revenue_gross": row["revenue"],
                "refunds_qty": row["ret_qty"],
                "refunds_amount": row["ret_amt"],
                "promo_cost": row["promo"],
                "delivery_cost": row["del_cost"],
                "commission_amount": row["comm"],
                "channel": row["channel"],
            }
            src_hash = _hash_payload(payload)

            stmt = insert(DailySales).values(
                d=row["d"],
                sku_id=sku_id,
                warehouse_id=wh_id,
                qty=row["qty"],
                revenue_gross=row["revenue"],
                refunds_qty=row["ret_qty"],
                refunds_amount=row["ret_amt"],
                promo_cost=row["promo"],
                delivery_cost=row["del_cost"],
                commission_amount=row["comm"],
                channel=row["channel"],
                src_hash=src_hash,
            )

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

    finally:
        await client.close()


async def collect_wb_stocks_now(db: Session) -> int:
    """Collect WB stocks snapshot (current day)."""
    settings = get_settings()
    client = WBClient(token=settings.wb_stats_token)

    today = date.today()
    log.info("wb_stocks_collection_started", extra={"date": str(today)})

    try:
        # WB stocks API requires dateFrom parameter
        response = await client.get_stocks(date_from=(today - timedelta(days=7)).isoformat())

        rows = norm_wb_stocks(response if isinstance(response, list) else [])

        upserts = 0
        for row in rows:
            sku_id = ensure_sku(db, "WB", nm_id=row["sku_key"])
            wh_id = ensure_warehouse(db, "WB", row["warehouse"]) if row["warehouse"] else None

            payload = {
                "d": str(row["d"]),
                "sku_id": sku_id,
                "warehouse_id": wh_id,
                "on_hand": row["on_hand"],
                "in_transit": row["in_transit"],
            }
            src_hash = _hash_payload(payload)

            if wh_id:  # Only insert if we have warehouse
                stmt = insert(DailyStock).values(
                    d=row["d"],
                    sku_id=sku_id,
                    warehouse_id=wh_id,
                    on_hand=row["on_hand"],
                    in_transit=row["in_transit"],
                    src_hash=src_hash,
                )

                if db.bind.dialect.name == "postgresql":
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["d", "sku_id", "warehouse_id"],
                        set_=dict(
                            on_hand=stmt.excluded.on_hand,
                            in_transit=stmt.excluded.in_transit,
                            src_hash=stmt.excluded.src_hash,
                        ),
                        where=(DailyStock.src_hash != stmt.excluded.src_hash),
                    )
                else:
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["d", "sku_id", "warehouse_id"],
                        set_=dict(
                            on_hand=stmt.excluded.on_hand,
                            in_transit=stmt.excluded.in_transit,
                            src_hash=stmt.excluded.src_hash,
                        ),
                    )

                db.execute(stmt)
                upserts += 1

        db.commit()

        log.info("wb_stocks_collection_completed", extra={"upserts": upserts, "date": str(today)})
        return upserts

    finally:
        await client.close()


async def collect_ozon_transactions_range(db: Session, d_from: date, d_to: date) -> int:
    """Collect Ozon transactions (cashflows) for date range."""
    settings = get_settings()
    client = OzonClient(client_id=settings.ozon_client_id, api_key=settings.ozon_api_key_admin)

    log.info("ozon_transactions_collection_started", extra={"from": str(d_from), "to": str(d_to)})

    try:
        # Ozon API uses pagination
        page = 1
        total_upserts = 0

        while True:
            response = await client.transactions(
                date_from=d_from.isoformat(),
                date_to=d_to.isoformat(),
                page=page,
                page_size=1000,
            )

            operations = response.get("result", {}).get("operations", [])
            if not operations:
                break

            rows = norm_ozon_transactions(response)

            for row in rows:
                payload = {
                    "d": str(row["d"]),
                    "marketplace": row["marketplace"],
                    "type": row["type"],
                    "amount": row["amount"],
                    "ref_id": row["ref_id"],
                }
                src_hash = _hash_payload(payload)

                stmt = insert(Cashflow).values(
                    d=row["d"],
                    marketplace=row["marketplace"],
                    type=row["type"],
                    amount=row["amount"],
                    ref_id=row["ref_id"],
                    src_hash=src_hash,
                )

                # Cashflow doesn't have unique constraint, using ref_id as proxy
                db.execute(stmt)
                total_upserts += 1

            # Check if there are more pages
            page_count = response.get("result", {}).get("page_count", page)
            if page >= page_count:
                break

            page += 1

        db.commit()

        log.info(
            "ozon_transactions_collection_completed",
            extra={"upserts": total_upserts, "from": str(d_from), "to": str(d_to)},
        )
        return total_upserts

    finally:
        await client.close()


async def collect_ozon_stocks_now(db: Session) -> int:
    """Collect Ozon stocks snapshot (current day)."""
    settings = get_settings()
    client = OzonClient(client_id=settings.ozon_client_id, api_key=settings.ozon_api_key_admin)

    today = date.today()
    log.info("ozon_stocks_collection_started", extra={"date": str(today)})

    try:
        page = 1
        total_upserts = 0

        while True:
            response = await client.stocks(page=page, page_size=1000)

            rows_data = response.get("result", {}).get("rows", [])
            if not rows_data:
                break

            rows = norm_ozon_stocks(response)

            for row in rows:
                sku_id = ensure_sku(db, "OZON", ozon_id=row["sku_key"])
                wh_id = ensure_warehouse(db, "OZON", row["warehouse"]) if row["warehouse"] else None

                payload = {
                    "d": str(row["d"]),
                    "sku_id": sku_id,
                    "warehouse_id": wh_id,
                    "on_hand": row["on_hand"],
                    "in_transit": row["in_transit"],
                }
                src_hash = _hash_payload(payload)

                if wh_id:
                    stmt = insert(DailyStock).values(
                        d=row["d"],
                        sku_id=sku_id,
                        warehouse_id=wh_id,
                        on_hand=row["on_hand"],
                        in_transit=row["in_transit"],
                        src_hash=src_hash,
                    )

                    if db.bind.dialect.name == "postgresql":
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["d", "sku_id", "warehouse_id"],
                            set_=dict(
                                on_hand=stmt.excluded.on_hand,
                                in_transit=stmt.excluded.in_transit,
                                src_hash=stmt.excluded.src_hash,
                            ),
                            where=(DailyStock.src_hash != stmt.excluded.src_hash),
                        )
                    else:
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["d", "sku_id", "warehouse_id"],
                            set_=dict(
                                on_hand=stmt.excluded.on_hand,
                                in_transit=stmt.excluded.in_transit,
                                src_hash=stmt.excluded.src_hash,
                            ),
                        )

                    db.execute(stmt)
                    total_upserts += 1

            # Check pagination
            has_next = response.get("result", {}).get("has_next", False)
            if not has_next:
                break

            page += 1

        db.commit()

        log.info(
            "ozon_stocks_collection_completed", extra={"upserts": total_upserts, "date": str(today)}
        )
        return total_upserts

    finally:
        await client.close()
