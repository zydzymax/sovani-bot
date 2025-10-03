"""Finance API endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.cashflow_pnl import (
    recompute_cashflow,
    recompute_pnl,
    run_reconciliation,
    run_scenario,
)
from app.web.deps import current_user, require_admin
from app.web.utils.exporters import to_csv

router = APIRouter(prefix="/api/v1/finance")

DBSession = Annotated[Session, Depends(get_db)]
AdminDep = Annotated[dict, Depends(require_admin)]
UserDep = Annotated[dict, Depends(current_user)]


class ScenarioRequest(BaseModel):
    sku_id: int
    new_price: float | None = None
    add_qty: int | None = None
    horizon_days: int = 28
    leadtime_days: int = 5


@router.post("/cashflow/compute")
def compute_cashflow(db: DBSession, admin: AdminDep, date_from: date, date_to: date):
    """Recompute cashflow (admin only)."""
    result = recompute_cashflow(db, date_from, date_to)
    return result


@router.post("/pnl/compute")
def compute_pnl(
    db: DBSession, admin: AdminDep, date_from: date, date_to: date, cost_strategy: str = "latest"
):
    """Recompute P&L (admin only)."""
    result = recompute_pnl(db, date_from, date_to, cost_strategy)
    return result


@router.post("/reconcile")
def reconcile(db: DBSession, admin: AdminDep, date_from: date, date_to: date):
    """Run commission reconciliation (admin only)."""
    result = run_reconciliation(db, date_from, date_to)
    return result


@router.post("/scenario")
def scenario(db: DBSession, user: UserDep, req: ScenarioRequest):
    """Run what-if scenario."""
    result = run_scenario(
        db, req.sku_id, req.new_price, req.add_qty, req.horizon_days, req.leadtime_days
    )
    return result


# Export endpoints
@router.get("/export/cashflow.csv")
def export_cashflow_csv(db: DBSession, user: UserDep, date_from: date, date_to: date):
    """Export cashflow as CSV."""
    query = text(
        "SELECT * FROM vw_cashflow_daily WHERE d BETWEEN :d1 AND :d2 ORDER BY d, marketplace"
    )
    rows = db.execute(query, {"d1": date_from, "d2": date_to}).mappings().all()
    headers = ["d", "marketplace", "inflow", "outflow", "net", "balance"]
    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cashflow.csv"},
    )


@router.get("/export/pnl.csv")
def export_pnl_csv(
    db: DBSession, user: UserDep, date_from: date, date_to: date, sku_id: int | None = None
):
    """Export P&L as CSV."""
    if sku_id:
        query = text(
            "SELECT * FROM vw_pnl_actual_daily WHERE d BETWEEN :d1 AND :d2 AND sku_id = :sid ORDER BY d DESC"
        )
        rows = db.execute(query, {"d1": date_from, "d2": date_to, "sid": sku_id}).mappings().all()
    else:
        query = text(
            "SELECT * FROM vw_pnl_actual_daily WHERE d BETWEEN :d1 AND :d2 ORDER BY d DESC LIMIT 5000"
        )
        rows = db.execute(query, {"d1": date_from, "d2": date_to}).mappings().all()

    headers = [
        "d",
        "sku_id",
        "article",
        "marketplace",
        "revenue_net",
        "cogs",
        "gross_profit",
        "margin_pct",
    ]
    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pnl.csv"},
    )
