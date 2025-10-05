#!/usr/bin/env python3
"""Collect data for the last 30 days from WB/Ozon APIs."""

import asyncio
from datetime import date, timedelta

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.ingestion_real import (
    collect_ozon_stocks_now,
    collect_ozon_transactions_range,
    collect_wb_sales_range,
    collect_wb_stocks_now,
)

log = get_logger("collect_recent_data")


async def main():
    """Collect data for last 30 days."""
    today = date.today()
    d_from = today - timedelta(days=30)
    d_to = today

    log.info(f"Collecting data from {d_from} to {d_to}")

    with SessionLocal() as db:
        try:
            # Collect WB data
            log.info("Collecting WB sales...")
            wb_sales_count = await collect_wb_sales_range(db, d_from, d_to)
            log.info(f"Collected {wb_sales_count} WB sales records")

            log.info("Collecting WB stocks...")
            wb_stocks_count = await collect_wb_stocks_now(db)
            log.info(f"Collected {wb_stocks_count} WB stock records")

            # Collect Ozon data
            log.info("Collecting Ozon transactions...")
            ozon_txn_count = await collect_ozon_transactions_range(db, d_from, d_to)
            log.info(f"Collected {ozon_txn_count} Ozon transaction records")

            log.info("Collecting Ozon stocks...")
            ozon_stocks_count = await collect_ozon_stocks_now(db)
            log.info(f"Collected {ozon_stocks_count} Ozon stock records")

            db.commit()
            log.info("Data collection completed successfully!")

        except Exception as e:
            db.rollback()
            log.error(f"Error during data collection: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    asyncio.run(main())
