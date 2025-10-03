"""Finance API endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.limits import check_export_limit, check_rate_limit
from app.db.session import get_db
from app.db.utils import exec_scoped
from app.services.cashflow_pnl import (
    recompute_cashflow,
    recompute_pnl,
    run_reconciliation,
    run_scenario,
)
from app.web.deps import OrgScope, current_user, require_admin
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
def compute_cashflow(
    org_id: OrgScope,
    db: DBSession,
    admin: AdminDep,
    date_from: date,
    date_to: date,
):
    """Recompute cashflow (admin only, org-scoped)."""
    check_rate_limit(db, org_id, key="finance_compute", quota_per_sec=1.0)
    result = recompute_cashflow(db, org_id=org_id, d_from=date_from, d_to=date_to)
    return result


@router.post("/pnl/compute")
def compute_pnl(
    org_id: OrgScope,
    db: DBSession,
    admin: AdminDep,
    date_from: date,
    date_to: date,
    cost_strategy: str = "latest",
):
    """Recompute P&L (admin only, org-scoped)."""
    check_rate_limit(db, org_id, key="finance_compute", quota_per_sec=1.0)
    result = recompute_pnl(db, org_id=org_id, d_from=date_from, d_to=date_to, cost_strategy=cost_strategy)
    return result


@router.post("/reconcile")
def reconcile(
    org_id: OrgScope,
    db: DBSession,
    admin: AdminDep,
    date_from: date,
    date_to: date,
):
    """Run commission reconciliation (admin only, org-scoped)."""
    check_rate_limit(db, org_id, key="finance_compute", quota_per_sec=1.0)
    result = run_reconciliation(db, org_id=org_id, d_from=date_from, d_to=date_to)
    return result


@router.post("/scenario")
def scenario(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    req: ScenarioRequest,
):
    """Run what-if scenario (org-scoped)."""
    result = run_scenario(
        db,
        org_id=org_id,
        sku_id=req.sku_id,
        new_price=req.new_price,
        add_qty=req.add_qty,
        horizon_days=req.horizon_days,
        leadtime_days=req.leadtime_days,
    )
    return result


# Export endpoints
@router.get("/export/cashflow.csv")
def export_cashflow_csv(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    date_from: date,
    date_to: date,
    limit: int = Query(5000, le=100000, description="Max rows to export"),
):
    """Export cashflow as CSV (org-scoped)."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_cashflow_daily
        WHERE org_id = :org_id
          AND d BETWEEN :d1 AND :d2
        ORDER BY d, marketplace
        LIMIT :limit
    """
    rows = exec_scoped(
        db,
        query,
        {"org_id": org_id, "d1": date_from, "d2": date_to, "limit": limit},
        org_id,
    ).mappings().all()

    headers = ["d", "org_id", "marketplace", "inflow", "outflow", "net", "balance"]
    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cashflow.csv"},
    )


@router.get("/export/pnl.csv")
def export_pnl_csv(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    date_from: date,
    date_to: date,
    sku_id: int | None = None,
    limit: int = Query(5000, le=100000, description="Max rows to export"),
):
    """Export P&L as CSV (org-scoped)."""
    check_export_limit(db, org_id, limit)

    if sku_id:
        query = """
            SELECT * FROM vw_pnl_actual_daily
            WHERE org_id = :org_id
              AND d BETWEEN :d1 AND :d2
              AND sku_id = :sid
            ORDER BY d DESC
            LIMIT :limit
        """
        params = {"org_id": org_id, "d1": date_from, "d2": date_to, "sid": sku_id, "limit": limit}
    else:
        query = """
            SELECT * FROM vw_pnl_actual_daily
            WHERE org_id = :org_id
              AND d BETWEEN :d1 AND :d2
            ORDER BY d DESC
            LIMIT :limit
        """
        params = {"org_id": org_id, "d1": date_from, "d2": date_to, "limit": limit}

    rows = exec_scoped(db, query, params, org_id).mappings().all()

    headers = [
        "d",
        "org_id",
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
