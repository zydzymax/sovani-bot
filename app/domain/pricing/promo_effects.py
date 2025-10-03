"""Promo effects measurement from historical data."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import TypedDict


class PromoLift(TypedDict):
    """Promo lift estimation result."""

    lift: float | None
    n: int
    quality: str  # "low" | "medium"


def _group_by_weekday(rows: list[dict]) -> dict[int, list[dict]]:
    """Group observations by weekday."""
    g: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        wd = int(r.get("weekday", 0))
        g[wd].append(r)
    return g


def measure_promo_lift(series: list[dict], window: int = 14) -> PromoLift:
    """Estimate relative sales lift during promo periods.

    Approach:
    - Identify promo days (promo_flag=True)
    - For each promo day, find baseline from same weekday in window before promo
    - Calculate lift = (units_promo - baseline_units) / baseline_units
    - Return average lift across all promo days with quality indicator

    Args:
        series: List of price-demand observations
        window: Days to look back for baseline (default 14)

    Returns:
        PromoLift dict with lift estimate, sample size, and quality

    """
    promo_days = [r for r in series if r.get("promo_flag")]

    if not promo_days:
        return {"lift": None, "n": 0, "quality": "low"}

    # Index by date for fast lookups
    by_date = {r["d"]: r for r in series}

    lifts = []

    for p in promo_days:
        wd = int(p["weekday"])

        # Find matching weekday observations before this promo day
        matches = [r for r in series if (r["d"] < p["d"] and r["weekday"] == wd)]

        # Take most recent window observations
        matches = sorted(matches, key=lambda x: x["d"], reverse=True)[:window]

        if not matches:
            continue

        # Calculate baseline units (average from matching days)
        baseline = mean(max(0, r["units"]) for r in matches)
        promo_units = max(0, p["units"])

        if baseline <= 0:
            continue

        # Calculate relative lift
        lift = (promo_units - baseline) / baseline
        lifts.append(lift)

    # Quality assessment
    if not lifts or len(lifts) < 3:
        return {
            "lift": mean(lifts) if lifts else None,
            "n": len(lifts),
            "quality": "low",
        }

    return {
        "lift": mean(lifts),
        "n": len(lifts),
        "quality": "medium",
    }
