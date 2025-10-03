"""Commission reconciliation."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def reconcile_commissions(
    db: Session, d_from: date, d_to: date, threshold_pct: float = 5.0
) -> list[dict]:
    """Reconcile actual vs calculated commissions."""
    query = text(
        """
        SELECT * FROM vw_commission_recon
        WHERE d BETWEEN :d1 AND :d2
          AND flag_outlier = 1
        ORDER BY ABS(delta_pct) DESC
    """
    )

    rows = db.execute(query, {"d1": d_from, "d2": d_to}).mappings().all()
    return [dict(r) for r in rows]
