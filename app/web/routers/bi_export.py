"""BI Export endpoints for Power BI/Metabase integration."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limits import check_export_limit
from app.db.session import get_db
from app.db.utils import exec_scoped
from app.web.deps import OrgScope, current_user
from app.web.utils.exporters import to_csv, to_xlsx

router = APIRouter()

settings = get_settings()


def limit_guard(limit: int = Query(default=5000, le=100000)) -> int:
    """Enforce limit constraints for BI exports."""
    max_rows = settings.bi_export_max_rows
    default_limit = settings.bi_export_default_limit

    if limit <= 0:
        return default_limit
    if limit > max_rows:
        return max_rows
    return limit


DBSession = Annotated[Session, Depends(get_db)]
UserDep = Annotated[dict, Depends(current_user)]


@router.get("/bi/pnl.csv")
def pnl_csv(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    date_from: date,
    date_to: date,
    sku_id: int | None = None,
    warehouse_id: int | None = None,
    marketplace: str | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export P&L data as CSV."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_pnl_daily
        WHERE org_id = :org_id
          AND d BETWEEN :d1 AND :d2
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:warehouse_id IS NULL OR warehouse_id = :warehouse_id)
          AND (:marketplace IS NULL OR marketplace = :marketplace)
        ORDER BY d, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {
                "d1": date_from,
                "d2": date_to,
                "sku_id": sku_id,
                "warehouse_id": warehouse_id,
                "marketplace": marketplace,
                "lim": limit,
                "off": offset,
            },
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "d",
        "sku_id",
        "article",
        "warehouse_id",
        "warehouse",
        "marketplace",
        "units",
        "revenue_net_gross",
        "revenue_net",
        "unit_cost",
        "profit_approx",
        "sv14",
        "sv28",
    ]

    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pnl.csv"},
    )


@router.get("/bi/pnl.xlsx")
def pnl_xlsx(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    date_from: date,
    date_to: date,
    sku_id: int | None = None,
    warehouse_id: int | None = None,
    marketplace: str | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export P&L data as XLSX."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_pnl_daily
        WHERE org_id = :org_id
          AND d BETWEEN :d1 AND :d2
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:warehouse_id IS NULL OR warehouse_id = :warehouse_id)
          AND (:marketplace IS NULL OR marketplace = :marketplace)
        ORDER BY d, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {
                "d1": date_from,
                "d2": date_to,
                "sku_id": sku_id,
                "warehouse_id": warehouse_id,
                "marketplace": marketplace,
                "lim": limit,
                "off": offset,
            },
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "d",
        "sku_id",
        "article",
        "warehouse_id",
        "warehouse",
        "marketplace",
        "units",
        "revenue_net_gross",
        "revenue_net",
        "unit_cost",
        "profit_approx",
        "sv14",
        "sv28",
    ]

    xlsx_content = to_xlsx([dict(r) for r in rows], headers, sheet_name="PnL")
    return Response(
        content=xlsx_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pnl.xlsx"},
    )


@router.get("/bi/inventory.csv")
def inventory_csv(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    sku_id: int | None = None,
    warehouse_id: int | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export inventory snapshot as CSV."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_inventory_snapshot
        WHERE org_id = :org_id
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:warehouse_id IS NULL OR warehouse_id = :warehouse_id)
        ORDER BY sku_id, warehouse_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {"sku_id": sku_id, "warehouse_id": warehouse_id, "lim": limit, "off": offset},
            org_id,
        )
        .mappings()
        .all()
    )

    headers = ["sku_id", "warehouse_id", "warehouse", "on_hand", "in_transit", "d"]

    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory.csv"},
    )


@router.get("/bi/inventory.xlsx")
def inventory_xlsx(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    sku_id: int | None = None,
    warehouse_id: int | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export inventory snapshot as XLSX."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_inventory_snapshot
        WHERE org_id = :org_id
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:warehouse_id IS NULL OR warehouse_id = :warehouse_id)
        ORDER BY sku_id, warehouse_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {"sku_id": sku_id, "warehouse_id": warehouse_id, "lim": limit, "off": offset},
            org_id,
        )
        .mappings()
        .all()
    )

    headers = ["sku_id", "warehouse_id", "warehouse", "on_hand", "in_transit", "d"]

    xlsx_content = to_xlsx([dict(r) for r in rows], headers, sheet_name="Inventory")
    return Response(
        content=xlsx_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=inventory.xlsx"},
    )


@router.get("/bi/supply_advice.csv")
def supply_advice_csv(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    sku_id: int | None = None,
    warehouse_id: int | None = None,
    window_days: int | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export supply advice as CSV."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_supply_advice
        WHERE org_id = :org_id
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:warehouse_id IS NULL OR warehouse_id = :warehouse_id)
          AND (:window_days IS NULL OR window_days = :window_days)
        ORDER BY d DESC, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {
                "sku_id": sku_id,
                "warehouse_id": warehouse_id,
                "window_days": window_days,
                "lim": limit,
                "off": offset,
            },
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "d",
        "sku_id",
        "article",
        "warehouse_id",
        "warehouse",
        "window_days",
        "recommended_qty",
        "rationale_hash",
    ]

    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=supply_advice.csv"},
    )


@router.get("/bi/supply_advice.xlsx")
def supply_advice_xlsx(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    sku_id: int | None = None,
    warehouse_id: int | None = None,
    window_days: int | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export supply advice as XLSX."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_supply_advice
        WHERE org_id = :org_id
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:warehouse_id IS NULL OR warehouse_id = :warehouse_id)
          AND (:window_days IS NULL OR window_days = :window_days)
        ORDER BY d DESC, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {
                "sku_id": sku_id,
                "warehouse_id": warehouse_id,
                "window_days": window_days,
                "lim": limit,
                "off": offset,
            },
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "d",
        "sku_id",
        "article",
        "warehouse_id",
        "warehouse",
        "window_days",
        "recommended_qty",
        "rationale_hash",
    ]

    xlsx_content = to_xlsx([dict(r) for r in rows], headers, sheet_name="Supply Advice")
    return Response(
        content=xlsx_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=supply_advice.xlsx"},
    )


@router.get("/bi/pricing_advice.csv")
def pricing_advice_csv(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    sku_id: int | None = None,
    quality: str | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export pricing advice as CSV."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_pricing_advice
        WHERE org_id = :org_id
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:quality IS NULL OR quality = :quality)
        ORDER BY expected_profit DESC, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {"sku_id": sku_id, "quality": quality, "lim": limit, "off": offset},
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "d",
        "sku_id",
        "article",
        "suggested_price",
        "suggested_discount_pct",
        "expected_profit",
        "quality",
        "reason_code",
        "rationale_hash",
    ]

    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pricing_advice.csv"},
    )


@router.get("/bi/pricing_advice.xlsx")
def pricing_advice_xlsx(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    sku_id: int | None = None,
    quality: str | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export pricing advice as XLSX."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_pricing_advice
        WHERE org_id = :org_id
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:quality IS NULL OR quality = :quality)
        ORDER BY expected_profit DESC, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {"sku_id": sku_id, "quality": quality, "lim": limit, "off": offset},
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "d",
        "sku_id",
        "article",
        "suggested_price",
        "suggested_discount_pct",
        "expected_profit",
        "quality",
        "reason_code",
        "rationale_hash",
    ]

    xlsx_content = to_xlsx([dict(r) for r in rows], headers, sheet_name="Pricing Advice")
    return Response(
        content=xlsx_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pricing_advice.xlsx"},
    )


@router.get("/bi/reviews_summary.csv")
def reviews_summary_csv(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    date_from: date | None = None,
    date_to: date | None = None,
    sku_id: int | None = None,
    marketplace: str | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export reviews summary as CSV."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_reviews_summary
        WHERE org_id = :org_id
          AND (:date_from IS NULL OR d >= :date_from)
          AND (:date_to IS NULL OR d <= :date_to)
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:marketplace IS NULL OR marketplace = :marketplace)
        ORDER BY d DESC, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {
                "date_from": date_from,
                "date_to": date_to,
                "sku_id": sku_id,
                "marketplace": marketplace,
                "lim": limit,
                "off": offset,
            },
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "marketplace",
        "sku_id",
        "article",
        "d",
        "reviews_total",
        "rating_avg",
        "replies_sent",
    ]

    csv_content = to_csv([dict(r) for r in rows], headers)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reviews_summary.csv"},
    )


@router.get("/bi/reviews_summary.xlsx")
def reviews_summary_xlsx(
    org_id: OrgScope,
    db: DBSession,
    user: UserDep,
    date_from: date | None = None,
    date_to: date | None = None,
    sku_id: int | None = None,
    marketplace: str | None = None,
    limit: int = Depends(limit_guard),
    offset: int = 0,
) -> Response:
    """Export reviews summary as XLSX."""
    check_export_limit(db, org_id, limit)

    query = """
        SELECT * FROM vw_reviews_summary
        WHERE org_id = :org_id
          AND (:date_from IS NULL OR d >= :date_from)
          AND (:date_to IS NULL OR d <= :date_to)
          AND (:sku_id IS NULL OR sku_id = :sku_id)
          AND (:marketplace IS NULL OR marketplace = :marketplace)
        ORDER BY d DESC, sku_id
        LIMIT :lim OFFSET :off
    """

    rows = (
        exec_scoped(
            db,
            query,
            {
                "date_from": date_from,
                "date_to": date_to,
                "sku_id": sku_id,
                "marketplace": marketplace,
                "lim": limit,
                "off": offset,
            },
            org_id,
        )
        .mappings()
        .all()
    )

    headers = [
        "marketplace",
        "sku_id",
        "article",
        "d",
        "reviews_total",
        "rating_avg",
        "replies_sent",
    ]

    xlsx_content = to_xlsx([dict(r) for r in rows], headers, sheet_name="Reviews Summary")
    return Response(
        content=xlsx_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reviews_summary.xlsx"},
    )
