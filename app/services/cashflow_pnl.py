"""Cashflow & PnL service facade."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.domain.finance.cashflow import build_daily_cashflow, upsert_cashflow_daily
from app.domain.finance.pnl_actual import compute_daily_pnl, upsert_pnl_daily
from app.domain.finance.recon import reconcile_commissions
from app.domain.finance.scenario import (
    simulate_combo,
    simulate_pricing_scenario,
    simulate_supply_scenario,
)


def recompute_cashflow(db: Session, *, org_id: int, d_from: date, d_to: date) -> dict:
    """Recompute cashflow (scoped to org)."""
    records = build_daily_cashflow(db, org_id, d_from, d_to)
    count = upsert_cashflow_daily(db, org_id, records)
    return {"status": "success", "records_processed": len(records), "records_upserted": count}


def recompute_pnl(
    db: Session, *, org_id: int, d_from: date, d_to: date, cost_strategy: str
) -> dict:
    """Recompute P&L (scoped to org)."""
    records = compute_daily_pnl(db, org_id, d_from, d_to, cost_strategy)
    count = upsert_pnl_daily(db, org_id, records)
    return {"status": "success", "records_processed": len(records), "records_upserted": count}


def run_reconciliation(db: Session, *, org_id: int, d_from: date, d_to: date) -> dict:
    """Run commission reconciliation (scoped to org)."""
    outliers = reconcile_commissions(db, org_id, d_from, d_to)
    return {"status": "success", "outliers_found": len(outliers), "outliers": outliers[:100]}


def run_scenario(
    db: Session,
    *,
    org_id: int,
    sku_id: int,
    new_price: float | None,
    add_qty: int | None,
    horizon_days: int,
    leadtime_days: int,
) -> dict:
    """Run what-if scenario (scoped to org)."""
    if new_price and add_qty:
        return simulate_combo(db, org_id, sku_id, new_price, add_qty, horizon_days, leadtime_days)
    elif new_price:
        return simulate_pricing_scenario(db, org_id, sku_id, new_price, horizon_days)
    elif add_qty:
        return simulate_supply_scenario(db, org_id, sku_id, add_qty, leadtime_days)
    return {"status": "error", "message": "Must specify new_price or add_qty"}
